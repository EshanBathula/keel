"""Cash-aware overlay: known scheduled cash from unpaid invoices.

The statistical models in models.py forecast "organic" revenue only — cash
whose timing and amount isn't already known. Unpaid invoices are the opposite
case: we know the exact amount and, if the customer pays on time, the exact
date (the due date). Layering this in separately (rather than blending it
into the statistical forecast) is what makes the projection "cash-aware, not
just revenue-aware" — see docs/DECISIONS.md for why double-counting is a
real risk here, not just a tidiness concern.
"""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Invoice, InvoiceStatus
from ..weekly import week_start

# Used when a customer has no paid-invoice history at all (brand new
# customer): assume the same on-time rate as the user's overall average,
# and if the user has literally no payment history yet, this floor.
DEFAULT_ON_TIME_RATE = 0.7
DEFAULT_LATE_WEEKS = 2


def _customer_payment_stats(db: Session, user_id: int) -> dict[int, tuple[float, float]]:
    """Per-customer (on_time_rate, avg_late_weeks) computed from their own
    paid-with-a-recorded-paid_date invoice history. Invoices predating the
    paid_date column (NULL) are excluded — we have no way to know if they
    were on time, and assuming so would fabricate a favorable statistic.
    """
    invoices = db.scalars(
        select(Invoice).where(
            Invoice.user_id == user_id,
            Invoice.status == InvoiceStatus.paid,
            Invoice.paid_date.isnot(None),
            Invoice.customer_id.isnot(None),
        )
    ).all()

    by_customer: dict[int, list[Invoice]] = defaultdict(list)
    for inv in invoices:
        by_customer[inv.customer_id].append(inv)

    stats = {}
    for customer_id, invs in by_customer.items():
        on_time = sum(1 for i in invs if i.paid_date <= i.due_date)
        rate = on_time / len(invs)
        late = [(i.paid_date - i.due_date).days / 7 for i in invs if i.paid_date > i.due_date]
        avg_late_weeks = sum(late) / len(late) if late else DEFAULT_LATE_WEEKS
        stats[customer_id] = (rate, avg_late_weeks)
    return stats


def _user_default_rate(stats: dict[int, tuple[float, float]]) -> float:
    if not stats:
        return DEFAULT_ON_TIME_RATE
    return sum(rate for rate, _ in stats.values()) / len(stats)


def scheduled_invoice_cash_cents(
    db: Session,
    user_id: int,
    week_starts: list[date],
    today: date | None = None,
) -> dict[date, int]:
    """Expected-value cash contribution per future week from currently unpaid
    invoices (status sent/overdue), keyed by week_start.

    Each invoice's amount is split between its due-date week (weighted by the
    customer's historical on-time rate) and a "late" week offset by that
    customer's average historical lateness — an expected-value model, not a
    full delay distribution (see docs/DECISIONS.md for why that's the
    right-sized amount of complexity here).
    """
    today = today or date.today()
    current_week = week_start(today)
    stats = _customer_payment_stats(db, user_id)
    default_rate = _user_default_rate(stats)

    horizon_starts = set(week_starts)
    contributions: dict[date, int] = defaultdict(int)

    unpaid = db.scalars(
        select(Invoice).where(
            Invoice.user_id == user_id,
            Invoice.status.in_((InvoiceStatus.sent, InvoiceStatus.overdue)),
        )
    ).all()
    for inv in unpaid:
        rate, avg_late_weeks = stats.get(inv.customer_id, (default_rate, DEFAULT_LATE_WEEKS))
        # An invoice already overdue has, by definition, missed its "on time"
        # week — clamp to the current week rather than silently dropping that
        # expected cash because its scheduled week is in the past.
        on_time_week = max(week_start(inv.due_date), current_week)
        late_week = max(week_start(inv.due_date + timedelta(weeks=round(avg_late_weeks))), current_week)

        on_time_share = round(inv.amount_cents * rate)
        late_share = inv.amount_cents - on_time_share

        if on_time_week in horizon_starts:
            contributions[on_time_week] += on_time_share
        if late_share and late_week in horizon_starts:
            contributions[late_week] += late_share

    return dict(contributions)
