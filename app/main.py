from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Field, Session, SQLModel, create_engine, select

# Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# ============================= SQL and Table Config ============================
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

# Data Models
class UserBase(SQLModel):
    name: str = Field(unique=True, index=True)
    email: str

class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str

class UserRead(UserBase):
    id: int

class UserCreate(UserBase):
    password: str  # Plaintext password from user input

# ===================================== JWT & OAuth Config =================================
app = FastAPI(lifespan=lifespan)

SECRET_KEY = "mysecret"
ALGORITHM = "HS256"
OAuth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ===================================== Endpoints =================================

@app.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserCreate, session: Session = Depends(get_session)):

    # Check if user already exists
    statement = select(User).where(User.name == user_data.name)
    existing_user = session.exec(statement).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Hash password and create user
    db_user = User(
        name=user_data.name,
        email=user_data.email,
        hashed_password=hash_password(user_data.password)
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

@app.post("/login")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session)
):

    # Retrieve user by username using select()
    statement = select(User).where(User.name == form_data.username)
    user = session.exec(statement).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username or password"
        )
    
    access_token = create_token({"sub": user.name})
    return {"access_token": access_token, "token_type": "bearer"}

def verify_token(
    token: Annotated[str, Depends(OAuth2_scheme)],
    session: Session = Depends(get_session)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    statement = select(User).where(User.name == username)
    user = session.exec(statement).first()
    
    if not user:
        raise credentials_exception
    return user

class Userout(SQLModel):
    id:int

@app.get("/users/me", response_model=Userout)
def get_me(current_user: Annotated[User, Depends(verify_token)]):
    return current_user