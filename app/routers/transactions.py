from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import TransCreate, TransRead, Transaction, User
from app.security import verify_token

router = APIRouter(prefix="/transaction", tags=["Transaction"])

@router.post(
    "s",
    response_model=TransRead,
    status_code=status.HTTP_201_CREATED,
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

@router.get("s", response_model=List[TransRead])
def get_transactions(
    current_user: Annotated[User, Depends(verify_token)],
    session: Session = Depends(get_session),
):
    statement = select(Transaction).where(Transaction.user_id == current_user.id)
    transactions = session.exec(statement).all()
    return transactions

@router.get("/{tid}", response_model=TransRead)
def get_trans_by_id(
    tid: int,
    current_user: Annotated[User, Depends(verify_token)],
    session: Session = Depends(get_session),
):
    statement = select(Transaction).where(
        Transaction.user_id == current_user.id,
        Transaction.id == tid,
    )
    transaction = session.exec(statement).first()
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    return transaction

@router.delete("/{tid}")
def del_transaction(
    tid: int,
    current_user: Annotated[User, Depends(verify_token)],
    session: Session = Depends(get_session),
):
    statement = select(Transaction).where(
        Transaction.user_id == current_user.id,
        Transaction.id == tid,
    )
    transaction = session.exec(statement).first()
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    session.delete(transaction)
    session.commit()
    return {"ok": True}