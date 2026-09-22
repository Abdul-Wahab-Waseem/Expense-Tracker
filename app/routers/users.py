from typing import Annotated
from fastapi import APIRouter, Depends

from app.models import User, Userout
from app.security import verify_token

router = APIRouter(prefix="/users", tags=["User"])

@router.get("/me", response_model=Userout)
def get_me(current_user: Annotated[User, Depends(verify_token)]):
    return current_user