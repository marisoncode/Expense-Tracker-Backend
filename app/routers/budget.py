from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import app.schemas as schemas
import app.models as models
from app.database import get_db
from app.services.budget_service import calculate_budget_summary

router = APIRouter(prefix="/api/v1/budget", tags=["budget"])

@router.put("/update")
async def update_budget(budget_update: schemas.BudgetUpdate, db: AsyncSession = Depends(get_db)):
    # Ensure user exists for foreign key constraint
    user_res = await db.execute(select(models.User).where(models.User.id == budget_update.user_id))
    if not user_res.scalar_one_or_none():
        user = models.User(
            id=budget_update.user_id,
            name="Default User",
            phone_number="0000000000",
            monthly_budget=0.0,
            theme_preference=models.ThemePreference.light
        )
        db.add(user)
        await db.commit()

    result = await db.execute(
        select(models.MonthlyBudget).where(
            models.MonthlyBudget.user_id == budget_update.user_id,
            models.MonthlyBudget.month == budget_update.month
        )
    )
    budget_record = result.scalars().first()
    
    if budget_record:
        budget_record.amount = budget_update.monthly_budget
    else:
        budget_record = models.MonthlyBudget(
            user_id=budget_update.user_id,
            month=budget_update.month,
            amount=budget_update.monthly_budget
        )
        db.add(budget_record)

    await db.commit()
    return {"message": "Budget updated successfully", "month": budget_update.month, "new_budget": budget_record.amount}

@router.get("/summary", response_model=schemas.BudgetSummary)
async def get_budget_summary(user_id: int, month: str, db: AsyncSession = Depends(get_db)):
    # month format: YYYY-MM
    try:
        year, month_num = map(int, month.split('-'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format, use YYYY-MM")
    
    summary = await calculate_budget_summary(user_id, year, month_num, db)
    return summary

@router.get("/dashboard-overview", response_model=schemas.DashboardOverview)
async def get_dashboard_overview(
    user_id: int = 1,
    month: str = "2026-08",
    limit_expenses: int = 50,
    db: AsyncSession = Depends(get_db)
):
    try:
        year, month_num = map(int, month.split('-'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format, use YYYY-MM")

    from app.services.budget_service import calculate_monthly_stats, calculate_category_breakdown, get_month_date_range

    m_start, m_end = get_month_date_range(year, month_num)

    budget_task = calculate_budget_summary(user_id, year, month_num, db)
    stats_task = calculate_monthly_stats(user_id, year, month_num, db)
    cats_task = calculate_category_breakdown(user_id, "month", year, month_num, None, None, None, db)
    
    # Recent expenses in this month
    exp_res = await db.execute(
        select(models.ExpenseLog)
        .where(
            models.ExpenseLog.user_id == user_id,
            models.ExpenseLog.date >= m_start,
            models.ExpenseLog.date <= m_end
        )
        .order_by(models.ExpenseLog.date.desc(), models.ExpenseLog.id.desc())
        .limit(limit_expenses)
    )
    expenses = exp_res.scalars().all()

    budget_summary = await budget_task
    stats = await stats_task
    categories = await cats_task

    return {
        "budget": budget_summary,
        "stats": stats,
        "categories": categories,
        "recent_expenses": expenses
    }

