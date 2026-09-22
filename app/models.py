from datetime import date
from enum import Enum
from typing import Optional
from sqlmodel import Field, Relationship, SQLModel

# --- User Models ---
class UserBase(SQLModel):
    name: str = Field(unique=True, index=True)
    email: str

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    transactions: list["Transaction"] = Relationship(back_populates="user")

class UserRead(UserBase):
    id: int

class UserCreate(UserBase):
    password: str

class Userout(SQLModel):
    id: int

# --- Category Models ---
class CatBase(SQLModel):
    categories: str

class Category(CatBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class CatRead(CatBase):
    id: int

class CatCreate(CatBase):
    categories: str

    class Config:
        json_schema_extra = {"examples": [{"categories": "Groceries"}]}

# --- Transaction Models ---
class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"

class TransBase(SQLModel):
    amount: float = Field(gt=0, description="Amount spent or earned")
    type: TransactionType = Field(description="Type should be Income or Expense")
    category: str
    description: Optional[str] = Field(default=None, description="If you want to add description")
    trans_date: date = Field(default_factory=date.today)

class Transaction(TransBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    user: Optional[User] = Relationship(back_populates="transactions")

class TransRead(TransBase):
    id: int
    user_id: Optional[int]

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