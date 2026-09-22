from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import CatCreate, CatRead, Category, User
from app.security import verify_token

router = APIRouter(prefix="/category", tags=["Category"])

@router.post("/", response_model=CatRead, status_code=status.HTTP_201_CREATED)
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

@router.get("/", response_model=List[CatRead])
def get_category(
    current_user: Annotated[User, Depends(verify_token)],
    session: Session = Depends(get_session),
):
    categories = session.exec(select(Category)).all()
    if not categories:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No categories exist")
    return categories