from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, extract, desc, asc
from sqlalchemy import func, desc, asc
from typing import Dict, Any, List, Optional
import calendar
from datetime import date, timedelta
import app.models as models

def get_month_date_range(year: int, month: int) -> tuple[date, date]:
    """Returns the start and end dates for a given month."""
    num_days = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, num_days)

def get_year_date_range(year: int) -> tuple[date, date]:
    """Returns the start and end dates for a given year."""
    return date(year, 1, 1), date(year, 12, 31)

async def calculate_budget_summary(user_id: int, year: int, month: int, db: AsyncSession) -> Dict[str, Any]:
    month_str = f"{year}-{month:02d}"
    start_date, end_date = get_month_date_range(year, month)
    
    # Get monthly budget for this specific month ONLY - strict per-month budget
    # Get monthly budget for this specific month ONLY - uses (user_id, month) index
    result_budget = await db.execute(
        select(models.MonthlyBudget).where(
        select(models.MonthlyBudget.amount).where(
            models.MonthlyBudget.user_id == user_id,
            models.MonthlyBudget.month == month_str
        )
    )
    monthly_budget_record = result_budget.scalars().first()
    monthly_budget = monthly_budget_record.amount if monthly_budget_record else 0.0
    monthly_budget = result_budget.scalar_one_or_none() or 0.0
    
    # Get total spent for the month
    # Get total spent for the month - uses (user_id, date) index range scan
    result_spent = await db.execute(
        select(func.sum(models.ExpenseLog.amount))
        .where(
            models.ExpenseLog.user_id == user_id,
            extract('year', models.ExpenseLog.date) == year,
            extract('month', models.ExpenseLog.date) == month
            models.ExpenseLog.date >= start_date,
            models.ExpenseLog.date <= end_date
        )
    )
    total_spent = float(result_spent.scalar() or 0.0)
    
    remaining_budget = monthly_budget - total_spent
    negative_balance = abs(remaining_budget) if remaining_budget < 0 else 0.0
    spent_percentage = round((total_spent / monthly_budget * 100), 1) if monthly_budget > 0 else 0.0
    
    return {
        "month": month_str,
        "total_budget": round(monthly_budget, 2),
        "total_spent": round(total_spent, 2),
        "remaining_budget": round(remaining_budget if remaining_budget >= 0 else 0.0, 2),
        "negative_balance": round(negative_balance, 2),
        "spent_percentage": spent_percentage,
        "is_over_budget": remaining_budget < 0
    }

async def calculate_category_breakdown(
    user_id: int,
    timeframe: str = "month",
    year: Optional[int] = None,
    month: Optional[int] = None,
    target_date: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = None
) -> List[Dict[str, Any]]:
    query = select(
        models.ExpenseLog.category,
        func.sum(models.ExpenseLog.amount).label("total"),
        func.count(models.ExpenseLog.id).label("count")
    ).where(models.ExpenseLog.user_id == user_id)

    if timeframe == "day" and target_date:
        query = query.where(models.ExpenseLog.date == target_date)
    elif timeframe == "range" and start_date and end_date:
        query = query.where(models.ExpenseLog.date >= start_date, models.ExpenseLog.date <= end_date)
    elif timeframe == "year" and year:
        query = query.where(extract('year', models.ExpenseLog.date) == year)
        y_start, y_end = get_year_date_range(year)
        query = query.where(models.ExpenseLog.date >= y_start, models.ExpenseLog.date <= y_end)
    elif timeframe == "month" and year and month:
        query = query.where(
            extract('year', models.ExpenseLog.date) == year,
            extract('month', models.ExpenseLog.date) == month
        )
        m_start, m_end = get_month_date_range(year, month)
        query = query.where(models.ExpenseLog.date >= m_start, models.ExpenseLog.date <= m_end)

    query = query.group_by(models.ExpenseLog.category).order_by(desc("total"))
    result = await db.execute(query)
    rows = result.all()
    
    overall_total = sum(r.total for r in rows) if rows else 0.0
    
    breakdown = []
    for r in rows:
        pct = round((r.total / overall_total * 100), 1) if overall_total > 0 else 0.0
        breakdown.append({
            "category": r.category,
            "total_spent": round(float(r.total), 2),
            "percentage": pct,
            "transaction_count": r.count
        })
    return breakdown

async def calculate_trend_analytics(
    user_id: int,
    timeframe: str, # "day", "month", "year", "range"
    year: int,
    month: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = None
) -> Dict[str, Any]:
    if timeframe == "day":
        # Day-wise trend for the specific month
        if not month:
            month = date.today().month
        
        num_days = calendar.monthrange(year, month)[1]
        m_start, m_end = get_month_date_range(year, month)
        num_days = m_end.day
        month_name = calendar.month_name[month]
        
        result = await db.execute(
            select(
                extract('day', models.ExpenseLog.date).label("d"),
                models.ExpenseLog.date,
                func.sum(models.ExpenseLog.amount).label("total"),
                func.count(models.ExpenseLog.id).label("count")
            )
            .where(
                models.ExpenseLog.user_id == user_id,
                extract('year', models.ExpenseLog.date) == year,
                extract('month', models.ExpenseLog.date) == month
                models.ExpenseLog.date >= m_start,
                models.ExpenseLog.date <= m_end
            )
            .group_by(extract('day', models.ExpenseLog.date))
            .group_by(models.ExpenseLog.date)
        )
        day_rows = {int(r.d): {"total": float(r.total), "count": int(r.count)} for r in result.all()}
        day_rows = {r.date.day: {"total": float(r.total), "count": int(r.count)} for r in result.all()}
        
        points = []
        total_period = 0.0
        for d in range(1, num_days + 1):
            data = day_rows.get(d, {"total": 0.0, "count": 0})
            points.append({
                "label": f"{d}",
                "date_key": f"{year}-{month:02d}-{d:02d}",
                "total_spent": round(data["total"], 2),
                "transaction_count": data["count"]
            })
            total_period += data["total"]

        return {
            "timeframe": "day",
            "period_label": f"{month_name} {year}",
            "total_period_spent": round(total_period, 2),
            "points": points
        }

    elif timeframe == "month":
        # Month-wise trend for the given year (Jan..Dec)
        y_start, y_end = get_year_date_range(year)
        
        # Optimized month grouping with range filter
        result = await db.execute(
            select(
                extract('month', models.ExpenseLog.date).label("m"),
                models.ExpenseLog.date,
                func.sum(models.ExpenseLog.amount).label("total"),
                func.count(models.ExpenseLog.id).label("count")
            )
            .where(
                models.ExpenseLog.user_id == user_id,
                extract('year', models.ExpenseLog.date) == year
                models.ExpenseLog.date >= y_start,
                models.ExpenseLog.date <= y_end
            )
            .group_by(extract('month', models.ExpenseLog.date))
            .group_by(models.ExpenseLog.date)
        )
        month_rows = {int(r.m): {"total": float(r.total), "count": int(r.count)} for r in result.all()}
        
        month_totals: Dict[int, Dict[str, float]] = {m: {"total": 0.0, "count": 0} for m in range(1, 13)}
        for r in result.all():
            m = r.date.month
            month_totals[m]["total"] += float(r.total)
            month_totals[m]["count"] += int(r.count)
        
        points = []
        total_period = 0.0
        month_abbrs = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for m in range(1, 13):
            data = month_rows.get(m, {"total": 0.0, "count": 0})
            data = month_totals[m]
            points.append({
                "label": month_abbrs[m - 1],
                "date_key": f"{year}-{m:02d}",
                "total_spent": round(data["total"], 2),
                "transaction_count": data["count"]
            })
            total_period += data["total"]

        return {
            "timeframe": "month",
            "period_label": f"Year {year}",
            "total_period_spent": round(total_period, 2),
            "points": points
        }

    elif timeframe == "range" and start_date and end_date:
        # Custom range trend
        result = await db.execute(
            select(
                models.ExpenseLog.date,
                func.sum(models.ExpenseLog.amount).label("total"),
                func.count(models.ExpenseLog.id).label("count")
            )
            .where(
                models.ExpenseLog.user_id == user_id,
                models.ExpenseLog.date >= start_date,
                models.ExpenseLog.date <= end_date
            )
            .group_by(models.ExpenseLog.date)
        )
        date_rows = {r.date: {"total": float(r.total), "count": int(r.count)} for r in result.all()}
        
        points = []
        total_period = 0.0
        curr = start_date
        while curr <= end_date:
            data = date_rows.get(curr, {"total": 0.0, "count": 0})
            points.append({
                "label": curr.strftime("%d %b"),
                "date_key": curr.strftime("%Y-%m-%d"),
                "total_spent": round(data["total"], 2),
                "transaction_count": data["count"]
            })
            total_period += data["total"]
            curr += timedelta(days=1)

        return {
            "timeframe": "range",
            "period_label": f"{start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')}",
            "total_period_spent": round(total_period, 2),
            "points": points
        }

    else: # "year"
        # Year-wise comparison
        current_year = date.today().year
        years = list(range(current_year - 4, current_year + 1))
        
        result = await db.execute(
            select(
                extract('year', models.ExpenseLog.date).label("y"),
                models.ExpenseLog.date,
                func.sum(models.ExpenseLog.amount).label("total"),
                func.count(models.ExpenseLog.id).label("count")
            )
            .where(
                models.ExpenseLog.user_id == user_id
            )
            .group_by(extract('year', models.ExpenseLog.date))
            .group_by(models.ExpenseLog.date)
        )
        year_rows = {int(r.y): {"total": float(r.total), "count": int(r.count)} for r in result.all()}
        
        all_db_years = sorted(set(years + list(year_rows.keys())))
        current_year = date.today().year
        years = list(range(current_year - 4, current_year + 1))
        
        year_totals: Dict[int, Dict[str, float]] = {}
        for r in result.all():
            y = r.date.year
            if y not in year_totals:
                year_totals[y] = {"total": 0.0, "count": 0}
            year_totals[y]["total"] += float(r.total)
            year_totals[y]["count"] += int(r.count)
            
        all_db_years = sorted(set(years + list(year_totals.keys())))
        
        points = []
        total_period = 0.0
        for y in all_db_years:
            data = year_rows.get(y, {"total": 0.0, "count": 0})
            data = year_totals.get(y, {"total": 0.0, "count": 0})
            points.append({
                "label": f"{y}",
                "date_key": f"{y}",
                "total_spent": round(data["total"], 2),
                "transaction_count": data["count"]
            })
            total_period += data["total"]

        return {
            "timeframe": "year",
            "period_label": "Multi-Year Comparison",
            "total_period_spent": round(total_period, 2),
            "points": points
        }

async def calculate_monthly_stats(user_id: int, year: int, month: int, db: AsyncSession) -> Dict[str, Any]:
    result = await db.execute(
        select(models.ExpenseLog)
        .where(
    start_date, end_date = get_month_date_range(year, month)
    
    # 1. Total spent & Transaction count using DB aggregation
    tot_res = await db.execute(
        select(
            func.coalesce(func.sum(models.ExpenseLog.amount), 0.0),
            func.count(models.ExpenseLog.id)
        ).where(
            models.ExpenseLog.user_id == user_id,
            extract('year', models.ExpenseLog.date) == year,
            extract('month', models.ExpenseLog.date) == month
            models.ExpenseLog.date >= start_date,
            models.ExpenseLog.date <= end_date
        )
    )
    expenses = result.scalars().all()
    tot_row = tot_res.one()
    total_spent = float(tot_row[0])
    tx_count = int(tot_row[1])
    
    if not expenses:
    if tx_count == 0:
        return {
            "total_spent": 0.0,
            "transaction_count": 0,
            "average_daily_spent": 0.0,
            "highest_expense_amount": 0.0,
            "highest_expense_title": None,
            "top_category": None,
            "top_category_amount": 0.0
        }
    
    total_spent = sum(e.amount for e in expenses)
    num_days = calendar.monthrange(year, month)[1]
    num_days = end_date.day
    avg_daily = total_spent / num_days
    
    highest_exp = max(expenses, key=lambda e: e.amount)
    # 2. Highest expense query (1 row index lookup)
    high_res = await db.execute(
        select(models.ExpenseLog.amount, models.ExpenseLog.category, models.ExpenseLog.notes)
        .where(
            models.ExpenseLog.user_id == user_id,
            models.ExpenseLog.date >= start_date,
            models.ExpenseLog.date <= end_date
        )
        .order_by(desc(models.ExpenseLog.amount))
        .limit(1)
    )
    high_row = high_res.first()
    highest_amount = float(high_row[0]) if high_row else 0.0
    highest_title = f"{high_row[1]} ({high_row[2] or 'Expense'})" if high_row else None
    
    cat_totals: Dict[str, float] = {}
    for e in expenses:
        cat_totals[e.category] = cat_totals.get(e.category, 0.0) + e.amount
    # 3. Top category query (DB group by + index)
    top_cat_res = await db.execute(
        select(models.ExpenseLog.category, func.sum(models.ExpenseLog.amount).label("cat_total"))
        .where(
            models.ExpenseLog.user_id == user_id,
            models.ExpenseLog.date >= start_date,
            models.ExpenseLog.date <= end_date
        )
        .group_by(models.ExpenseLog.category)
        .order_by(desc("cat_total"))
        .limit(1)
    )
    top_cat_row = top_cat_res.first()
    top_category = top_cat_row[0] if top_cat_row else None
    top_category_amount = float(top_cat_row[1]) if top_cat_row else 0.0
    
    top_cat = max(cat_totals.items(), key=lambda x: x[1]) if cat_totals else (None, 0.0)
    
    return {
        "total_spent": round(total_spent, 2),
        "transaction_count": len(expenses),
        "transaction_count": tx_count,
        "average_daily_spent": round(avg_daily, 2),
        "highest_expense_amount": round(highest_exp.amount, 2),
        "highest_expense_title": f"{highest_exp.category} ({highest_exp.notes or 'Expense'})",
        "top_category": top_cat[0],
        "top_category_amount": round(top_cat[1], 2)
        "highest_expense_amount": round(highest_amount, 2),
        "highest_expense_title": highest_title,
        "top_category": top_category,
        "top_category_amount": round(top_category_amount, 2)
    }

async def get_month_daily_spending(user_id: int, year: int, month: int, db: AsyncSession) -> Dict[str, Any]:
    start_date, end_date = get_month_date_range(year, month)
    
    result = await db.execute(
        select(
            models.ExpenseLog.date,
            func.sum(models.ExpenseLog.amount).label("daily_total")
        )
        .where(
            models.ExpenseLog.user_id == user_id,
            extract('year', models.ExpenseLog.date) == year,
            extract('month', models.ExpenseLog.date) == month
            models.ExpenseLog.date >= start_date,
            models.ExpenseLog.date <= end_date
        )
        .group_by(models.ExpenseLog.date)
    )
    rows = result.all()
    
    daily_map = {r.date.strftime("%Y-%m-%d"): round(float(r.daily_total), 2) for r in rows}
    total_spent = sum(daily_map.values())
    
    return {
        "month": f"{year}-{month:02d}",
        "daily_totals": daily_map,
        "total_month_spent": round(total_spent, 2)
    }

async def calculate_monthly_comparison(user_id: int, year: int, db: AsyncSession) -> Dict[str, Any]:
    y_start, y_end = get_year_date_range(year)
    
    # Query monthly budgets for all months of this year
    budget_res = await db.execute(
        select(models.MonthlyBudget).where(
        select(models.MonthlyBudget.month, models.MonthlyBudget.amount).where(
            models.MonthlyBudget.user_id == user_id,
            models.MonthlyBudget.month.like(f"{year}-%")
        )
    )
    budgets = {b.month: b.amount for b in budget_res.scalars().all()}
    budgets = {row[0]: float(row[1]) for row in budget_res.all()}

    # Query monthly spending and counts for this year
    # Query monthly spending and counts for this year using index range scan
    spend_res = await db.execute(
        select(
            extract('month', models.ExpenseLog.date).label("month_num"),
            models.ExpenseLog.date,
            func.sum(models.ExpenseLog.amount).label("total_spent"),
            func.count(models.ExpenseLog.id).label("tx_count")
        )
        .where(
            models.ExpenseLog.user_id == user_id,
            extract('year', models.ExpenseLog.date) == year
            models.ExpenseLog.date >= y_start,
            models.ExpenseLog.date <= y_end
        )
        .group_by(extract('month', models.ExpenseLog.date))
        .group_by(models.ExpenseLog.date)
    )
    spending_by_month = {int(r.month_num): (float(r.total_spent), int(r.tx_count)) for r in spend_res.all()}
    
    spending_by_month: Dict[int, list] = {m: [0.0, 0] for m in range(1, 13)}
    for r in spend_res.all():
        m_num = r.date.month
        spending_by_month[m_num][0] += float(r.total_spent)
        spending_by_month[m_num][1] += int(r.tx_count)

    now = date.today()
    current_year = now.year
    current_month_num = now.month

    months_data = []
    yearly_total = 0.0

    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    for m_idx, m_name in enumerate(month_names, start=1):
        m_key = f"{year}-{m_idx:02d}"
        spent, cnt = spending_by_month.get(m_idx, (0.0, 0))
        spent, cnt = spending_by_month[m_idx]
        b_amt = budgets.get(m_key, 0.0)
        yearly_total += spent

        months_data.append({
            "month_key": m_key,
            "month_num": m_idx,
            "month_name": m_name,
            "short_month": m_name[:3],
            "year": year,
            "total_spent": round(spent, 2),
            "transaction_count": cnt,
            "budget": round(b_amt, 2),
            "is_current_month": (year == current_year and m_idx == current_month_num)
        })

    max_spent = max((m["total_spent"] for m in months_data), default=0.0)
    peak_month_item = max(months_data, key=lambda m: m["total_spent"]) if max_spent > 0 else None
    active_months = [m for m in months_data if m["total_spent"] > 0 or (year == current_year and m["month_num"] <= current_month_num)]
    avg_monthly = (yearly_total / len(active_months)) if active_months else 0.0

    for m in months_data:
        m["percentage_of_peak"] = round((m["total_spent"] / max_spent * 100), 1) if max_spent > 0 else 0.0
        m["percentage_of_year"] = round((m["total_spent"] / yearly_total * 100), 1) if yearly_total > 0 else 0.0

    return {
        "year": year,
        "yearly_total_spent": round(yearly_total, 2),
        "average_monthly_spent": round(avg_monthly, 2),
        "peak_month": peak_month_item["month_name"] if peak_month_item and peak_month_item["total_spent"] > 0 else None,
        "peak_amount": round(max_spent, 2),
        "months": months_data
    }

