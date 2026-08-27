from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import AsyncSessionLocal
import logging
from app.services.telegram_service import (
    send_daily_digest,
    send_monthly_digest,
    send_yearly_digest
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def scheduled_daily_digest_job():
    logger.info("Executing scheduled Daily Telegram Digest...")
    async with AsyncSessionLocal() as db:
        try:
            await send_daily_digest(db)
        except Exception as e:
            logger.error(f"Error in scheduled daily digest: {e}")

async def scheduled_monthly_digest_job():
    logger.info("Executing scheduled Monthly Telegram Digest with PDF Statement...")
    async with AsyncSessionLocal() as db:
        try:
            await send_monthly_digest(db)
        except Exception as e:
            logger.error(f"Error in scheduled monthly digest: {e}")

async def scheduled_yearly_digest_job():
    logger.info("Executing scheduled Yearly Telegram Review with Annual PDF Statement...")
    async with AsyncSessionLocal() as db:
        try:
            await send_yearly_digest(db)
        except Exception as e:
            logger.error(f"Error in scheduled yearly digest: {e}")

def start_scheduler():
    # 1. Daily digest at 12:00 AM (Midnight) every day
    scheduler.add_job(
        scheduled_daily_digest_job,
        'cron',
        hour=0,
        minute=0,
        id="daily_telegram_digest",
        replace_existing=True
    )

    # 2. Monthly digest on the 1st day of every month at 12:00 AM
    scheduler.add_job(
        scheduled_monthly_digest_job,
        'cron',
        day=1,
        hour=0,
        minute=0,
        id="monthly_telegram_digest",
        replace_existing=True
    )

    # 3. Yearly digest on January 1st at 12:00 AM
    scheduler.add_job(
        scheduled_yearly_digest_job,
        'cron',
        month=1,
        day=1,
        hour=0,
        minute=0,
        id="yearly_telegram_digest",
        replace_existing=True
    )

    scheduler.start()
    logger.info("SpendWise Telegram Notification Scheduler started (Daily, Monthly & Yearly jobs configured).")
