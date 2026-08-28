from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from .database import Base

class ThemePreference(str, enum.Enum):
    dark = "dark"
    light = "light"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    phone_number = Column(String, unique=True, index=True)
    monthly_budget = Column(Float, default=0.0)
    theme_preference = Column(Enum(ThemePreference), default=ThemePreference.light)

    expense_logs = relationship("ExpenseLog", back_populates="user", cascade="all, delete-orphan")
    monthly_budgets = relationship("MonthlyBudget", back_populates="user", cascade="all, delete-orphan")

class ExpenseLog(Base):
    __tablename__ = "expense_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date, index=True)
    amount = Column(Float, nullable=False)
    category = Column(String, index=True, nullable=False)
    payment_method = Column(String, default="UPI") # UPI, Cash, Credit Card, Debit Card, Net Banking
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="expense_logs")

class MonthlyBudget(Base):
    __tablename__ = "monthly_budgets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    month = Column(String, index=True) # Format: YYYY-MM
    amount = Column(Float, default=0.0)

    user = relationship("User", back_populates="monthly_budgets")
