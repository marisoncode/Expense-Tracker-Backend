import asyncio
import os
import sys

# Ensure the backend directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base, AsyncSessionLocal
from app.models import User

async def seed():
    print("Resetting database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        
    print("Tables created. Initializing clean default user...")
    async with AsyncSessionLocal() as db:
        # Create primary User with clean slate (0.0 budget, no hardcoded transactions)
        user = User(
            name="User",
            phone_number="1234567890",
            monthly_budget=0.0
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(f"Created User: {user.name} (ID: {user.id}) with initial Monthly Budget: Rs {user.monthly_budget}")
        print("\nClean database initialized successfully with no hardcoded amounts or expenses!")

if __name__ == "__main__":
    asyncio.run(seed())
