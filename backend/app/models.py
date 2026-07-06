"""SQLAlchemy ORM models for Keel."""
import enum
from datetime import datetime, date

from sqlalchemy import String, Integer, Date, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .money import to_cents, to_dollars


class TxType(str, enum.Enum):
    income = "income"
    expense = "expense"


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    paid = "paid"
    overdue = "overdue"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    business_name: Mapped[str] = mapped_column(String(255), default="My Business")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    customers: Mapped[list["Customer"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="customers")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="customer")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="customer")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    type: Mapped[TxType] = mapped_column(Enum(TxType), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)  # always positive; type determines sign
    category: Mapped[str] = mapped_column(String(100), index=True, default="Uncategorized")
    description: Mapped[str] = mapped_column(String(500), default="")
    date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="transactions")
    customer: Mapped["Customer | None"] = relationship(back_populates="transactions")

    @property
    def amount(self) -> float:
        """Dollar view of amount_cents, for schemas and call sites built around dollars."""
        return to_dollars(self.amount_cents)

    @amount.setter
    def amount(self, dollars) -> None:
        self.amount_cents = to_cents(dollars)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    number: Mapped[str] = mapped_column(String(50))
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.draft, index=True)
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="invoices")
    customer: Mapped["Customer | None"] = relationship(back_populates="invoices")

    @property
    def amount(self) -> float:
        return to_dollars(self.amount_cents)

    @amount.setter
    def amount(self, dollars) -> None:
        self.amount_cents = to_cents(dollars)
