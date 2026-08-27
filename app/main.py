from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import engine, Base
from app.routers import expenses, budget, calendar, notifications
from app.services.scheduler import start_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB (creates all tables including users, expense_logs, monthly_budgets)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Start the background scheduler
    start_scheduler()
    yield
    pass

app = FastAPI(title="SpendWise - Expense & Budget Tracker API", lifespan=lifespan)

import os

# Add CORS Middleware for React frontend
cors_origins_env = os.getenv("CORS_ORIGINS", "*")
origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in origins else origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(expenses.router)
app.include_router(budget.router)
app.include_router(calendar.router)
app.include_router(notifications.router)

@app.get("/")
def read_root():
    return {
        "app": "SpendWise - Expense & Budget Tracker API",
        "status": "healthy",
        "version": "2.0.0"
    }
