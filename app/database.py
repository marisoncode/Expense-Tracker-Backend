from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

raw_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./budget.db")

connect_args = {}

if "postgresql" in raw_db_url or "postgres" in raw_db_url:
    # Normalize scheme to postgresql+asyncpg
    if raw_db_url.startswith("postgresql://"):
        db_url = raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif raw_db_url.startswith("postgres://"):
        db_url = raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    else:
        db_url = raw_db_url

    # Strip query parameters (sslmode, channel_binding) as asyncpg uses connect_args for SSL
    if "?" in db_url:
        DATABASE_URL = db_url.split("?")[0]
    else:
        DATABASE_URL = db_url

    # Enable SSL for cloud PostgreSQL (Neon, Supabase, Render)
    connect_args["ssl"] = True
elif "sqlite" in raw_db_url:
    DATABASE_URL = raw_db_url
    connect_args["check_same_thread"] = False
else:
    DATABASE_URL = raw_db_url

engine_kwargs = {
    "echo": False,
    "connect_args": connect_args,
}

# PostgreSQL connection pool tuning for cloud/serverless DBs (Neon/Supabase)
if "postgresql" in DATABASE_URL:
    engine_kwargs.update({
        "pool_pre_ping": True,     # Test connection liveness to prevent dead socket hangs
        "pool_recycle": 300,       # Recycle connections every 5 mins to stay ahead of server timeouts
        "pool_size": 10,           # Pre-warmed persistent connection pool
        "max_overflow": 20,        # Allow burst concurrency without blocking
        "pool_timeout": 30         # 30-second timeout on waiting for connections
    })

engine = create_async_engine(
    DATABASE_URL, 
    **engine_kwargs
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

