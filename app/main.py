from fastapi import FastAPI

from app.database import lifespan
from app.routers import auth, categories, transactions, users

app = FastAPI(lifespan=lifespan)

# Include all modular routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(categories.router)
app.include_router(transactions.router)