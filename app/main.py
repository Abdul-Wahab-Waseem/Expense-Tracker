from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select

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

# ============================= Data Models ============================
class UserBase(SQLModel):
    name: str = Field(unique=True, index=True)
    email: str

class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str
    transactions: list["Transaction"] = Relationship(back_populates="user")

class UserRead(UserBase):
    id: int

class UserCreate(UserBase):
    password: str  # Plaintext password from user input

# Category Entity
class CatBase(SQLModel):
    categories: str

class Category(CatBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

class CatRead(CatBase):
    id: int

class CatCreate(CatBase):
    categories: str

    class Config:
        json_schema_extra = {"examples": [{"categories": "Groceries"}]}


# Transaction Db config
class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class TransBase(SQLModel):
    amount: float = Field(gt=0, description="Amount spent or earned")  # Changed to float
    type: TransactionType = Field(description="Type should be Income or Expense")
    category: str
    description: Optional[str] = Field(default=None, description="If you want to add description")
    trans_date: date = Field(default_factory=date.today)


class Transaction(TransBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id")
    user: Optional[User] = Relationship(back_populates="transactions")


class TransRead(TransBase):
    id: int
    user_id: int | None


class TransCreate(TransBase):
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "amount": 45.5,
                    "type": "expense",
                    "category": "Groceries",
                    "description": "Weekly supermarket run",
                    "trans_date": "2026-09-22",
                }
            ]
        }


# ===================================== JWT & OAuth Config =================================
app = FastAPI(lifespan=lifespan)

SECRET_KEY = "mysecret"
ALGORITHM = "HS256"
OAuth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ===================================== Endpoints =================================

@app.post(
    "/signup",
    response_model=UserRead, 
    status_code=status.HTTP_201_CREATED,
    tags=["Sign-Up"],
    )
def signup(user_data: UserCreate, session: Session = Depends(get_session)):
    statement = select(User).where(User.name == user_data.name)
    existing_user = session.exec(statement).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    db_user = User(
        name=user_data.name,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

@app.post("/login",tags=["Login"])
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session),
):
    statement = select(User).where(User.name == form_data.username)
    user = session.exec(statement).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username or password",
        )
    access_token = create_token({"sub": user.name})
    return {"access_token": access_token, "token_type": "bearer"}

def verify_token(
    token: Annotated[str, Depends(OAuth2_scheme)],
    session: Session = Depends(get_session),
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
    id: int

@app.get("/users/me", response_model=Userout,tags=["User"])
def get_me(current_user: Annotated[User, Depends(verify_token)]):
    return current_user


@app.post("/category/", response_model=CatRead,tags=["Category"])
def create_category(
    current_user: Annotated[User, Depends(verify_token)],
    cat_data: CatCreate,
    session: Session = Depends(get_session),
):
    db_cat = Category.model_validate(cat_data)
    session.add(db_cat)
    session.commit()
    session.refresh(db_cat)
    return db_cat


@app.get("/category/", response_model=List[CatRead],tags=["Category"])
def get_category(
    current_user: Annotated[User, Depends(verify_token)],
    session: Session = Depends(get_session),
):
    categories = session.exec(select(Category)).all()
    if not categories:
        raise HTTPException(status_code=404, detail="No data exists")
    return categories


# Transaction Endpoints
@app.post(
    "/transactions",
    response_model=TransRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Transaction"],
)
def create_transaction(
    current_user: Annotated[User, Depends(verify_token)],
    trans_data: TransCreate,
    session: Session = Depends(get_session),
):
    db_trans = Transaction.model_validate(
        trans_data, update={"user_id": current_user.id}
    )
    session.add(db_trans)
    session.commit()
    session.refresh(db_trans)
    return db_trans

@app.get("/transaction/",response_model=List[TransRead],tags=["Transaction"])
def get_transaction(
    current_user: Annotated[User, Depends(verify_token)],
    session:Session = Depends(get_session)):
    statement = select(Transaction).where(Transaction.user_id == current_user.id)
    transaction = session.exec(statement)
    if not transaction:
        raise HTTPException(
            status_code=400,
            detail="No data exist"
        )
    return transaction

@app.get("/transaction/{tid}",response_model=TransRead,tags=["Transaction"])
def get_trans_by_id(
    tid:int,
    current_user: Annotated[User, Depends(verify_token)],
    session:Session = Depends(get_session)
    ):
    statement = select(Transaction).where(
        Transaction.user_id == current_user.id,
        Transaction.id == tid,
        )
    transaction = session.exec(statement).first()
    if not transaction:
        raise HTTPException(
            status_code=400,
            detail="No data exist"
        )
    return transaction

@app.delete("/transaction/{tid}",tags=["Transaction"])
def del_transaction(
    tid:int,
    current_user: Annotated[User, Depends(verify_token)],
    session:Session = Depends(get_session)
):
    statement = select(Transaction).where(
        Transaction.user_id == current_user.id,
        Transaction.id == tid,
    )
    transaction = session.exec(statement).first()
    if not transaction:
        raise HTTPException(
            status_code=400,
            detail="This type of data is not exist"
        )
    session.delete(transaction)
    session.commit()
    return{
        "ok" : True
    }