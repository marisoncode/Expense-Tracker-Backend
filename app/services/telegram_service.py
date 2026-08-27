import os
import httpx
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List
from sqlalchemy.future import select
from sqlalchemy import extract, desc
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

CATEGORY_EMOJIS = {
    "Food": "🍔",
    "Petrol": "⛽",
    "Dress": "👗",
    "Accessories": "🕶️",
    "Cinema": "🎬",
    "Other Expenses": "📦"
}

def get_category_emoji(cat: str) -> str:
    for k, v in CATEGORY_EMOJIS.items():
        if k.lower() == (cat or "").lower():
            return v
    return "💸"

async def send_telegram_message(html_text: str) -> bool:
    """Send an HTML-formatted message to the configured Telegram chat."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram Bot Token or Chat ID not configured.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": html_text,
        "parse_mode": "HTML"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=10.0)
            if response.status_code == 200:
                logger.info("Telegram notification delivered successfully.")
                return True
            else:
                logger.error(f"Telegram error {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to deliver Telegram message: {e}")
            return False

async def send_telegram_document(pdf_bytes: bytes, filename: str, caption: str = "") -> bool:
    """Send a PDF file attachment with a caption to the configured Telegram chat."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram Bot Token or Chat ID not configured.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption,
        "parse_mode": "HTML"
    }
    files = {
        "document": (filename, pdf_bytes, "application/pdf")
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, data=data, files=files, timeout=25.0)
            if response.status_code == 200:
                logger.info(f"Telegram document '{filename}' delivered successfully.")
                return True
            else:
                logger.error(f"Telegram sendDocument error {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to deliver Telegram document: {e}")
            return False

async def send_transaction_alert(
    expense_data: dict,
    budget_summary: Optional[dict] = None,
    action: str = "created"
):
    """
    Sends an instant notification when an expense is created, updated, or deleted.
    """
    emoji = get_category_emoji(expense_data.get("category", ""))
    amt = expense_data.get("amount", 0.0)
    cat = expense_data.get("category", "Other Expenses")
    pm = expense_data.get("payment_method", "UPI")
    dt = expense_data.get("date", "")
    notes = expense_data.get("notes") or "No description"

    if action == "created":
        header = "💸 <b>New Expense Logged!</b>"
    elif action == "updated":
        header = "✏️ <b>Expense Updated!</b>"
    elif action == "deleted":
        header = "🗑️ <b>Expense Removed!</b>"
    else:
        header = "📋 <b>Expense Notice</b>"

    message = f"{header}\n\n"
    message += f"🏷️ <b>Category:</b> {cat} {emoji}\n"
    message += f"💰 <b>Amount:</b> <b>₹{amt:,.2f}</b>\n"
    message += f"💳 <b>Payment:</b> {pm}\n"
    message += f"📅 <b>Date:</b> {dt}\n"
    message += f"📝 <b>Notes:</b> <i>{notes}</i>\n"

    if budget_summary and budget_summary.get("total_budget", 0) > 0:
        total_budget = budget_summary["total_budget"]
        total_spent = budget_summary["total_spent"]
        spent_pct = budget_summary["spent_percentage"]
        is_over = budget_summary["is_over_budget"]
        rem = budget_summary["remaining_budget"]
        neg_bal = budget_summary["negative_balance"]

        message += f"\n📊 <b>Monthly Budget Health:</b>\n"
        message += f"🎯 Target: ₹{total_budget:,.2f}\n"
        message += f"📉 Total Spent: ₹{total_spent:,.2f} ({spent_pct}%)\n"

        if is_over:
            message += f"🚨 <b>Status: OVER BUDGET by ₹{neg_bal:,.2f}</b>"
        else:
            message += f"✅ <b>Status: ₹{rem:,.2f} Remaining</b>"

    await send_telegram_message(message)

async def send_daily_digest(db: AsyncSession, target_date: Optional[date] = None, user_id: int = 1):
    """
    Summarizes transactions for a given day (defaults to yesterday if run at 12:00 AM).
    """
    import app.models as models
    from app.services.budget_service import calculate_budget_summary

    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    result = await db.execute(
        select(models.ExpenseLog)
        .where(models.ExpenseLog.user_id == user_id, models.ExpenseLog.date == target_date)
        .order_by(desc(models.ExpenseLog.amount))
    )
    expenses = result.scalars().all()
    total_spent = sum(e.amount for e in expenses)

    date_str = target_date.strftime("%d %B %Y (%A)")
    message = f"🌙 <b>Daily Spending Digest</b>\n"
    message += f"📅 <b>{date_str}</b>\n\n"

    if not expenses:
        message += "🎉 <b>Zero expenses recorded today!</b> Great job saving.\n"
    else:
        message += f"💰 <b>Total Spent Today:</b> <b>₹{total_spent:,.2f}</b> across {len(expenses)} transactions\n\n"
        message += "<b>Itemized Transactions:</b>\n"
        for idx, exp in enumerate(expenses, 1):
            emoji = get_category_emoji(exp.category)
            notes = f" - <i>{exp.notes}</i>" if exp.notes else ""
            message += f"{idx}. {emoji} {exp.category}: <b>₹{exp.amount:,.2f}</b> ({exp.payment_method or 'UPI'}){notes}\n"

    # Add monthly progress
    b_summary = await calculate_budget_summary(user_id, target_date.year, target_date.month, db)
    if b_summary and b_summary.get("total_budget", 0) > 0:
        message += f"\n📊 <b>Month Progress ({target_date.strftime('%B %Y')}):</b>\n"
        message += f"Spent ₹{b_summary['total_spent']:,.2f} of ₹{b_summary['total_budget']:,.2f} ({b_summary['spent_percentage']}%)\n"
        if b_summary["is_over_budget"]:
            message += f"⚠️ <b>Over budget by ₹{b_summary['negative_balance']:,.2f}</b>"
        else:
            message += f"✅ <b>₹{b_summary['remaining_budget']:,.2f} Remaining</b>"

    await send_telegram_message(message)

async def send_monthly_digest(db: AsyncSession, year: Optional[int] = None, month: Optional[int] = None, user_id: int = 1):
    """
    Sends the full monthly report and attaches the official PDF Statement!
    """
    import app.models as models
    from app.services.budget_service import calculate_budget_summary, calculate_category_breakdown
    from app.services.pdf_service import generate_expenses_pdf

    if year is None or month is None:
        # Defaults to the month that just ended
        today = date.today()
        first_of_this_month = date(today.year, today.month, 1)
        last_month_last_day = first_of_this_month - timedelta(days=1)
        year = last_month_last_day.year
        month = last_month_last_day.month

    month_dt = datetime(year, month, 1)
    month_name = month_dt.strftime("%B %Y")

    # Fetch all transactions
    result = await db.execute(
        select(models.ExpenseLog)
        .where(
            models.ExpenseLog.user_id == user_id,
            extract('year', models.ExpenseLog.date) == year,
            extract('month', models.ExpenseLog.date) == month
        )
        .order_by(models.ExpenseLog.date)
    )
    expenses = result.scalars().all()
    total_spent = sum(e.amount for e in expenses)

    b_summary = await calculate_budget_summary(user_id, year, month, db)
    cat_summary = await calculate_category_breakdown(user_id, "month", year, month, None, None, None, db)

    message = f"🏆 <b>Monthly Expense Summary - {month_name}</b>\n\n"
    message += f"💰 <b>Total Spent:</b> <b>₹{total_spent:,.2f}</b>\n"
    message += f"🧾 <b>Total Transactions:</b> {len(expenses)}\n\n"

    if b_summary and b_summary.get("total_budget", 0) > 0:
        budget_amt = b_summary["total_budget"]
        is_over = b_summary["is_over_budget"]
        message += f"🎯 <b>Budget Target:</b> ₹{budget_amt:,.2f}\n"
        if is_over:
            message += f"🚨 <b>Result: OVER BUDGET by ₹{b_summary['negative_balance']:,.2f}</b>\n\n"
        else:
            message += f"🎉 <b>Result: UNDER BUDGET! Saved ₹{b_summary['remaining_budget']:,.2f}</b>\n\n"

    if cat_summary:
        message += "📊 <b>Category Breakdown:</b>\n"
        for item in cat_summary:
            emoji = get_category_emoji(item["category"])
            message += f"• {emoji} {item['category']}: <b>₹{item['total_spent']:,.2f}</b> ({item['percentage']}%)\n"

    message += f"\n📄 <i>Your official {month_name} Statement PDF is attached below:</i>"

    # Generate PDF and attach to Telegram
    pdf_bytes = generate_expenses_pdf(
        expenses=expenses,
        period_title=month_name,
        budget_summary=b_summary,
        category_summary=cat_summary
    )
    pdf_filename = f"{month_dt.strftime('%B_%Y')}_Statement.pdf"

    await send_telegram_document(
        pdf_bytes=pdf_bytes,
        filename=pdf_filename,
        caption=message
    )

async def send_yearly_digest(db: AsyncSession, year: Optional[int] = None, user_id: int = 1):
    """
    Sends the annual financial review and attaches the official Yearly PDF Statement!
    """
    import app.models as models
    from app.services.budget_service import calculate_category_breakdown
    from app.services.pdf_service import generate_expenses_pdf

    if year is None:
        year = date.today().year - 1

    result = await db.execute(
        select(models.ExpenseLog)
        .where(
            models.ExpenseLog.user_id == user_id,
            extract('year', models.ExpenseLog.date) == year
        )
        .order_by(models.ExpenseLog.date)
    )
    expenses = result.scalars().all()
    total_spent = sum(e.amount for e in expenses)

    cat_summary = await calculate_category_breakdown(user_id, "year", year, None, None, None, None, db)

    message = f"🎆 <b>Annual Financial Review - Year {year}</b>\n\n"
    message += f"💰 <b>Total Yearly Expenses:</b> <b>₹{total_spent:,.2f}</b>\n"
    message += f"🧾 <b>Total Transactions:</b> {len(expenses)}\n\n"

    if cat_summary:
        message += "📊 <b>Yearly Category Distribution:</b>\n"
        for item in cat_summary:
            emoji = get_category_emoji(item["category"])
            message += f"• {emoji} {item['category']}: <b>₹{item['total_spent']:,.2f}</b> ({item['percentage']}%)\n"

    message += f"\n📄 <i>Your official {year} Annual Statement PDF is attached below:</i>"

    pdf_bytes = generate_expenses_pdf(
        expenses=expenses,
        period_title=f"Year {year}",
        budget_summary=None,
        category_summary=cat_summary
    )
    pdf_filename = f"{year}_Statement.pdf"

    await send_telegram_document(
        pdf_bytes=pdf_bytes,
        filename=pdf_filename,
        caption=message
    )
