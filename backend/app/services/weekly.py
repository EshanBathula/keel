"""Weekly transaction aggregation — the modeling substrate for services/forecast.

Weekly, not monthly, buckets are used for the forecasting engine: more data
points per business cycle means more signal for trend/seasonality detection
and a meaningful rolling-origin backtest. User-facing reporting still happens
at the monthly grain (see analytics.py) since that's what owners think in.
"""
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Transaction, TxType

INVOICE_PAYMENT_CATEGORY = "Invoice payment"


def week_start(d: date) -> date:
    """The Monday that starts the week containing `d`."""
    return d - timedelta(days=d.weekday())


def add_months(d: date, months: int) -> date:
    """Calendar-exact month addition (no external dependency needed)."""
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    next_month_start = date(year + (1 if month == 12 else 0), (month % 12) + 1, 1)
    days_in_month = (next_month_start - date(year, month, 1)).days
    return date(year, month, min(d.day, days_in_month))


def weekly_series_cents(db: Session, user_id: int, weeks: int, today: date | None = None) -> list[dict]:
    """Revenue (split organic vs. invoice-payment) and expenses in integer
    cents per week, trailing `weeks` weeks (inclusive of the current,
    possibly-partial, week).

    Revenue is split so the forecasting engine can model "organic" (not yet
    invoiced/tracked) revenue statistically while known invoice cash is
    layered on top explicitly instead of being double-counted — see
    services/forecast/cash.py.
    """
    today = today or date.today()
    current_start = week_start(today)
    starts = [current_start - timedelta(weeks=(weeks - 1 - i)) for i in range(weeks)]

    organic_rev: dict[date, int] = defaultdict(int)
    invoiced_rev: dict[date, int] = defaultdict(int)
    exp: dict[date, int] = defaultdict(int)
    txs = db.scalars(select(Transaction).where(Transaction.user_id == user_id)).all()
    for tx in txs:
        s = week_start(tx.date)
        if tx.type == TxType.income:
            if tx.category == INVOICE_PAYMENT_CATEGORY:
                invoiced_rev[s] += tx.amount_cents
            else:
                organic_rev[s] += tx.amount_cents
        else:
            exp[s] += tx.amount_cents

    return [
        {
            "week_start": s,
            "organic_revenue_cents": organic_rev[s],
            "invoiced_revenue_cents": invoiced_rev[s],
            "revenue_cents": organic_rev[s] + invoiced_rev[s],
            "expenses_cents": exp[s],
        }
        for s in starts
    ]
