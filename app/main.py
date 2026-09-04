from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import engine, Base
from app.routers import expenses, budget, calendar, notifications
from app.services.scheduler import start_scheduler

from sqlalchemy.future import select
from app.database import engine, Base, AsyncSessionLocal
import app.models as models
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB (creates all tables including users, expense_logs, monthly_budgets)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Auto-seed default user (id=1) in PostgreSQL/SQLite if not already present
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(models.User).where(models.User.id == 1))
            default_user = result.scalar_one_or_none()
            if not default_user:
                default_user = models.User(
                    id=1,
                    name="Default User",
                    phone_number="0000000000",
                    monthly_budget=0.0,
                    theme_preference=models.ThemePreference.light
                )
                session.add(default_user)
                await session.commit()
    except Exception as e:
        print("User initialization warning:", e)

    # Start the background scheduler
    start_scheduler()
    yield
    pass

app = FastAPI(title="SpendWise - Expense & Budget Tracker API", lifespan=lifespan)

# Add CORS Middleware for React frontend (Supports Vercel, localhost, and custom domains)
cors_origins_env = os.getenv("CORS_ORIGINS", "*")
origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in origins else origins,
    allow_origin_regex=r"https://.*\.vercel\.app" if "*" not in origins else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(expenses.router)
app.include_router(budget.router)
app.include_router(calendar.router)
app.include_router(notifications.router)

@app.api_route("/", methods=["GET", "POST", "HEAD"])
@app.api_route("/health", methods=["GET", "POST", "HEAD"])
@app.api_route("/api/v1", methods=["GET", "POST", "HEAD"])
@app.api_route("/api/v1/health", methods=["GET", "POST", "HEAD"])
@app.api_route("/ping", methods=["GET", "POST", "HEAD"])
def health_check():
    return {
        "app": "SpendWise - Expense & Budget Tracker API",
        "status": "healthy",
        "version": "2.0.0"
    }

