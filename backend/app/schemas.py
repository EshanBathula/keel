"""Pydantic schemas (request/response models)."""
from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

from .models import TxType, InvoiceStatus


# ---------- Auth ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    business_name: str = "My Business"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    business_name: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Customers ----------
class CustomerCreate(BaseModel):
    name: str
    email: str = ""
    notes: str = ""


class CustomerOut(CustomerCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- Transactions ----------
class TransactionCreate(BaseModel):
    type: TxType
    amount: float = Field(gt=0)
    category: str = "Uncategorized"
    description: str = ""
    date: date
    customer_id: int | None = None


class TransactionOut(TransactionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- Invoices ----------
class InvoiceCreate(BaseModel):
    customer_id: int | None = None
    number: str
    amount: float = Field(gt=0)
    status: InvoiceStatus = InvoiceStatus.draft
    issue_date: date
    due_date: date


class InvoiceUpdate(BaseModel):
    status: InvoiceStatus


class InvoiceOut(InvoiceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- Analytics ----------
class MonthlyPoint(BaseModel):
    month: str  # YYYY-MM
    revenue: float
    expenses: float
    net: float


class KPIs(BaseModel):
    revenue_this_month: float
    revenue_last_month: float
    revenue_growth_pct: float | None
    expenses_this_month: float
    net_this_month: float
    profit_margin_pct: float | None
    avg_monthly_burn: float
    cash_runway_months: float | None
    outstanding_receivables: float
    overdue_receivables: float
    health_score: int
    health_grade: str


class ForecastPoint(BaseModel):
    month: str
    projected_revenue: float
    projected_expenses: float
    projected_net: float
    lower: float
    upper: float


class Insight(BaseModel):
    id: str
    severity: str  # "opportunity" | "warning" | "critical" | "positive"
    title: str
    detail: str
    estimated_impact: str | None = None
