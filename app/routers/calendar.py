from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import date
import app.models as models
import app.schemas as schemas
from app.database import get_db
from app.services.budget_service import get_month_daily_spending

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])

@router.get("/day-summary", response_model=schemas.DaySummary)
async def get_day_summary(user_id: int, target_date: date, db: AsyncSession = Depends(get_db)):
    # Fetch expenses for the day
    result_expenses = await db.execute(
        select(models.ExpenseLog)
        .where(models.ExpenseLog.user_id == user_id, models.ExpenseLog.date == target_date)
        .order_by(models.ExpenseLog.id.desc())
    )
    expenses = result_expenses.scalars().all()
    
    total_spent = sum(exp.amount for exp in expenses)
    
    return {
        "date": target_date,
        "expenses": expenses,
        "total_spent": round(total_spent, 2)
    }

@router.get("/month-overview", response_model=schemas.DailySpendingOverview)
async def get_month_overview(
    user_id: int = Query(1),
    month: str = Query(..., description="Format YYYY-MM"),
    db: AsyncSession = Depends(get_db)
):
    try:
        year, month_num = map(int, month.split('-'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format, use YYYY-MM")

    return await get_month_daily_spending(user_id, year, month_num, db)
