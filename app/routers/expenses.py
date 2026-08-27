from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import extract, desc, asc, or_
from typing import List, Optional
from datetime import date, datetime
import csv
import io
import app.schemas as schemas
import app.models as models
from app.database import get_db
from app.services.budget_service import (
    calculate_category_breakdown,
    calculate_monthly_stats,
    calculate_trend_analytics,
    calculate_budget_summary,
    calculate_monthly_comparison
)
from app.services.pdf_service import generate_expenses_pdf
from app.services.telegram_service import send_transaction_alert

router = APIRouter(prefix="/api/v1/expenses", tags=["expenses"])

@router.post("", response_model=schemas.ExpenseLog)
async def create_expense(expense: schemas.ExpenseLogCreate, db: AsyncSession = Depends(get_db)):
    db_expense = models.ExpenseLog(**expense.model_dump())
    db.add(db_expense)
    await db.commit()
    await db.refresh(db_expense)

    # Trigger Telegram Alert
    try:
        b_summary = await calculate_budget_summary(db_expense.user_id, db_expense.date.year, db_expense.date.month, db)
        await send_transaction_alert({
            "category": db_expense.category,
            "amount": db_expense.amount,
            "payment_method": db_expense.payment_method,
            "date": db_expense.date.strftime("%d %b %Y"),
            "notes": db_expense.notes
        }, b_summary, action="created")
    except Exception as e:
        pass

    return db_expense

@router.get("", response_model=List[schemas.ExpenseLog])
async def list_expenses(
    user_id: int = Query(1),
    month: Optional[str] = Query(None, description="Format YYYY-MM"),
    year: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    payment_method: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    sort_by: Optional[str] = Query("date_desc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    query = select(models.ExpenseLog).where(models.ExpenseLog.user_id == user_id)

    if month:
        try:
            y, m_num = map(int, month.split("-"))
            query = query.where(
                extract('year', models.ExpenseLog.date) == y,
                extract('month', models.ExpenseLog.date) == m_num
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid month format, use YYYY-MM")
    elif year:
        query = query.where(extract('year', models.ExpenseLog.date) == year)

    if category:
        query = query.where(models.ExpenseLog.category == category)

    if payment_method:
        query = query.where(models.ExpenseLog.payment_method == payment_method)

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                models.ExpenseLog.category.ilike(search_pattern),
                models.ExpenseLog.notes.ilike(search_pattern),
                models.ExpenseLog.payment_method.ilike(search_pattern)
            )
        )

    if start_date:
        query = query.where(models.ExpenseLog.date >= start_date)

    if end_date:
        query = query.where(models.ExpenseLog.date <= end_date)

    # Sorting
    if sort_by == "date_asc":
        query = query.order_by(asc(models.ExpenseLog.date), asc(models.ExpenseLog.id))
    elif sort_by == "amount_desc":
        query = query.order_by(desc(models.ExpenseLog.amount))
    elif sort_by == "amount_asc":
        query = query.order_by(asc(models.ExpenseLog.amount))
    else: # default date_desc
        query = query.order_by(desc(models.ExpenseLog.date), desc(models.ExpenseLog.id))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/analytics/categories", response_model=List[schemas.CategoryBreakdownItem])
async def get_category_analytics(
    user_id: int = Query(1),
    timeframe: str = Query("month", description="day, month, year, range, or all"),
    month: Optional[str] = Query(None, description="Format YYYY-MM for month timeframe"),
    year: Optional[int] = Query(None),
    target_date: Optional[date] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    y = year
    m = None

    if month:
        try:
            y, m = map(int, month.split("-"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid month format, use YYYY-MM")
    elif not y and timeframe in ("month", "day", "year"):
        y = date.today().year
        m = date.today().month

    return await calculate_category_breakdown(
        user_id=user_id,
        timeframe=timeframe,
        year=y,
        month=m,
        target_date=target_date,
        start_date=start_date,
        end_date=end_date,
        db=db
    )

@router.get("/analytics/trends", response_model=schemas.TrendAnalytics)
async def get_trend_analytics(
    user_id: int = Query(1),
    timeframe: str = Query("day", description="day, month, year, or range"),
    month: Optional[str] = Query(None, description="Format YYYY-MM"),
    year: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    today = date.today()
    y = year or today.year
    m = today.month

    if month:
        try:
            y, m = map(int, month.split("-"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid month format, use YYYY-MM")

    return await calculate_trend_analytics(
        user_id=user_id,
        timeframe=timeframe,
        year=y,
        month=m,
        start_date=start_date,
        end_date=end_date,
        db=db
    )

@router.get("/analytics/stats", response_model=schemas.MonthlyStats)
async def get_monthly_stats(
    user_id: int = Query(1),
    month: str = Query(..., description="Format YYYY-MM"),
    db: AsyncSession = Depends(get_db)
):
    try:
        y, m_num = map(int, month.split("-"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format, use YYYY-MM")

    return await calculate_monthly_stats(user_id, y, m_num, db)

@router.get("/analytics/monthly-comparison", response_model=schemas.MonthlyComparisonResponse)
async def get_monthly_comparison(
    user_id: int = Query(1),
    year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    target_year = year or date.today().year
    return await calculate_monthly_comparison(user_id, target_year, db)

@router.get("/export/csv")
async def export_expenses_csv(
    user_id: int = Query(1),
    month: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    query = select(models.ExpenseLog).where(models.ExpenseLog.user_id == user_id).order_by(desc(models.ExpenseLog.date))
    file_base = "SpendWise_All_Time_Statement"

    if month:
        try:
            y, m_num = map(int, month.split("-"))
            query = query.where(
                extract('year', models.ExpenseLog.date) == y,
                extract('month', models.ExpenseLog.date) == m_num
            )
            month_dt = datetime(y, m_num, 1)
            file_base = f"{month_dt.strftime('%B_%Y')}_Statement"
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid month format, use YYYY-MM")
    elif start_date and end_date:
        query = query.where(models.ExpenseLog.date >= start_date, models.ExpenseLog.date <= end_date)
        if start_date == end_date:
            file_base = f"{start_date.strftime('%d_%B_%Y')}_Statement"
        else:
            file_base = f"{start_date.strftime('%d_%b_%Y')}_to_{end_date.strftime('%d_%b_%Y')}_Statement"
    elif year:
        query = query.where(extract('year', models.ExpenseLog.date) == year)
        file_base = f"{year}_Statement"

    if category:
        query = query.where(models.ExpenseLog.category == category)
        file_base += f"_{category}"

    result = await db.execute(query)
    expenses = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Date", "Category", "Amount (INR)", "Payment Method", "Notes"])

    for exp in expenses:
        writer.writerow([exp.id, exp.date.strftime("%Y-%m-%d"), exp.category, f"{exp.amount:.2f}", exp.payment_method or "UPI", exp.notes or ""])

    output.seek(0)
    filename = f"{file_base}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/export/pdf")
async def export_expenses_pdf(
    user_id: int = Query(1),
    month: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    query = select(models.ExpenseLog).where(models.ExpenseLog.user_id == user_id).order_by(desc(models.ExpenseLog.date))
    period_title = "All-Time Statement"
    file_base = "SpendWise_All_Time_Statement"
    budget_summary = None
    category_summary = None

    if month:
        try:
            y, m_num = map(int, month.split("-"))
            query = query.where(
                extract('year', models.ExpenseLog.date) == y,
                extract('month', models.ExpenseLog.date) == m_num
            )
            month_dt = datetime(y, m_num, 1)
            # Full month name and year: e.g. "August 2026"
            period_title = month_dt.strftime("%B %Y")
            file_base = f"{month_dt.strftime('%B_%Y')}_Statement"
            budget_summary = await calculate_budget_summary(user_id, y, m_num, db)
            category_summary = await calculate_category_breakdown(user_id, "month", y, m_num, None, None, None, db)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid month format, use YYYY-MM")
    elif start_date and end_date:
        query = query.where(models.ExpenseLog.date >= start_date, models.ExpenseLog.date <= end_date)
        if start_date == end_date:
            period_title = start_date.strftime("%d %B %Y")
            file_base = f"{start_date.strftime('%d_%B_%Y')}_Statement"
        else:
            period_title = f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"
            file_base = f"{start_date.strftime('%d_%b_%Y')}_to_{end_date.strftime('%d_%b_%Y')}_Statement"
        category_summary = await calculate_category_breakdown(user_id, "range", None, None, None, start_date, end_date, db)
    elif year:
        query = query.where(extract('year', models.ExpenseLog.date) == year)
        # Whole year: e.g. "2026" or "2007"
        period_title = f"Year {year}"
        file_base = f"{year}_Statement"
        category_summary = await calculate_category_breakdown(user_id, "year", year, None, None, None, None, db)

    if category:
        query = query.where(models.ExpenseLog.category == category)
        period_title += f" ({category})"
        file_base += f"_{category}"

    result = await db.execute(query)
    expenses = result.scalars().all()

    pdf_bytes = generate_expenses_pdf(
        expenses=expenses,
        period_title=period_title,
        budget_summary=budget_summary,
        category_summary=category_summary
    )

    clean_name = f"{file_base}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={clean_name}",
            "Content-Type": "application/pdf"
        }
    )

@router.get("/{expense_id}", response_model=schemas.ExpenseLog)
async def get_expense(expense_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.ExpenseLog).where(models.ExpenseLog.id == expense_id))
    expense = result.scalars().first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense

@router.put("/{expense_id}", response_model=schemas.ExpenseLog)
async def update_expense(
    expense_id: int,
    expense_update: schemas.ExpenseLogUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(models.ExpenseLog).where(models.ExpenseLog.id == expense_id))
    db_expense = result.scalars().first()
    if not db_expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    update_data = expense_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_expense, key, value)

    await db.commit()
    await db.refresh(db_expense)

    try:
        b_summary = await calculate_budget_summary(db_expense.user_id, db_expense.date.year, db_expense.date.month, db)
        await send_transaction_alert({
            "category": db_expense.category,
            "amount": db_expense.amount,
            "payment_method": db_expense.payment_method,
            "date": db_expense.date.strftime("%d %b %Y"),
            "notes": db_expense.notes
        }, b_summary, action="updated")
    except Exception:
        pass

    return db_expense

@router.delete("/{expense_id}")
async def delete_expense(expense_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.ExpenseLog).where(models.ExpenseLog.id == expense_id))
    db_expense = result.scalars().first()
    if not db_expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    deleted_info = {
        "category": db_expense.category,
        "amount": db_expense.amount,
        "payment_method": db_expense.payment_method,
        "date": db_expense.date.strftime("%d %b %Y"),
        "notes": db_expense.notes
    }
    user_id = db_expense.user_id
    exp_year = db_expense.date.year
    exp_month = db_expense.date.month

    await db.delete(db_expense)
    await db.commit()

    try:
        b_summary = await calculate_budget_summary(user_id, exp_year, exp_month, db)
        await send_transaction_alert(deleted_info, b_summary, action="deleted")
    except Exception:
        pass

    return {"message": "Expense deleted successfully", "id": expense_id}
