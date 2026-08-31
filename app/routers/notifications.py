from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.telegram_service import (
    send_telegram_message,
    send_daily_digest,
    send_monthly_digest,
    send_yearly_digest
)
from datetime import date

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

@router.api_route("/test-telegram", methods=["GET", "POST"])
async def test_telegram_notification():
    """
    Sends an instant verification message to confirm the Telegram Bot and Chat ID are working.
    Supports both GET and POST requests.
    """
    test_msg = (
        "🚀 <b>SpendWise Telegram Bot Connected!</b>\n\n"
        "✅ Notifications are active and configured.\n"
        "• 💸 Instant alerts on every transaction added/edited\n"
        "• 🌙 Daily spending digest at 11:59 PM with PDF statement\n"
        "• 🏆 Monthly summary + PDF statement at month-end\n"
        "• 🎆 Annual financial wrap-up at year-end\n\n"
        "<i>SpendWise Expense Tracker</i>"
    )
    success = await send_telegram_message(test_msg)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to send Telegram message. Please check your BOT_TOKEN and CHAT_ID in .env."
        )
    return {"status": "success", "message": "Test notification delivered to Telegram!"}

@router.api_route("/trigger-daily", methods=["GET", "POST"])
async def trigger_daily_digest(
    user_id: int = Query(1),
    target_date: str = Query(None, description="YYYY-MM-DD format (defaults to today/yesterday)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually triggers the Daily Spending Digest + PDF Statement to Telegram.
    Supports both GET (browser/cron) and POST.
    """
    t_date = None
    if target_date:
        try:
            t_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    await send_daily_digest(db, target_date=t_date, user_id=user_id)
    return {"status": "success", "message": "Daily digest & PDF statement dispatched to Telegram!"}

@router.api_route("/trigger-monthly", methods=["GET", "POST"])
async def trigger_monthly_digest(
    user_id: int = Query(1),
    year: int = Query(None),
    month: int = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually triggers the Monthly Digest + Attached PDF Statement to Telegram.
    Supports both GET and POST.
    """
    await send_monthly_digest(db, year=year, month=month, user_id=user_id)
    return {"status": "success", "message": "Monthly digest & PDF statement dispatched to Telegram!"}

@router.api_route("/trigger-yearly", methods=["GET", "POST"])
async def trigger_yearly_digest(
    user_id: int = Query(1),
    year: int = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually triggers the Annual Review + Attached PDF Statement to Telegram.
    Supports both GET and POST.
    """
    await send_yearly_digest(db, year=year, user_id=user_id)
    return {"status": "success", "message": "Yearly review & PDF statement dispatched to Telegram!"}

