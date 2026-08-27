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
