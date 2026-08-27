from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict
from datetime import date, datetime
from .models import ThemePreference

# --- User Schemas ---
class UserBase(BaseModel):
    name: str
    phone_number: str
    monthly_budget: float
    theme_preference: ThemePreference = ThemePreference.light

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- ExpenseLog Schemas ---
class ExpenseLogBase(BaseModel):
    date: date
    amount: float
    category: str
    payment_method: Optional[str] = "UPI"
    notes: Optional[str] = None

class ExpenseLogCreate(ExpenseLogBase):
    user_id: int

class ExpenseLogUpdate(BaseModel):
    date: Optional[date] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None

class ExpenseLog(ExpenseLogBase):
    id: int
    user_id: int
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

# --- Budget & Summary Schemas ---
class BudgetSummary(BaseModel):
    month: str
    total_budget: float
    total_spent: float
    remaining_budget: float
    negative_balance: float
    spent_percentage: float
    is_over_budget: bool

class BudgetUpdate(BaseModel):
    user_id: int
    monthly_budget: float
    month: str

# --- Analytics Schemas ---
class CategoryBreakdownItem(BaseModel):
    category: str
    total_spent: float
    percentage: float
    transaction_count: int

class MonthlyStats(BaseModel):
    total_spent: float
    transaction_count: int
    average_daily_spent: float
    highest_expense_amount: float
    highest_expense_title: Optional[str] = None
    top_category: Optional[str] = None
    top_category_amount: float = 0.0

class TrendPoint(BaseModel):
    label: str
    date_key: str
    total_spent: float
    transaction_count: int

class TrendAnalytics(BaseModel):
    timeframe: str # "day", "month", "year"
    period_label: str
    total_period_spent: float
    points: List[TrendPoint]

class MonthlyComparisonItem(BaseModel):
    month_key: str
    month_num: int
    month_name: str
    short_month: str
    year: int
    total_spent: float
    transaction_count: int
    budget: float
    is_current_month: bool
    percentage_of_peak: float
    percentage_of_year: float

class MonthlyComparisonResponse(BaseModel):
    year: int
    yearly_total_spent: float
    average_monthly_spent: float
    peak_month: Optional[str] = None
    peak_amount: float = 0.0
    months: List[MonthlyComparisonItem]

# --- Calendar Schemas ---
class DaySummary(BaseModel):
    date: date
    expenses: List[ExpenseLog]
    total_spent: float

class DailySpendingOverview(BaseModel):
    month: str
    daily_totals: Dict[str, float] # { "YYYY-MM-DD": total_spent }
    total_month_spent: float
