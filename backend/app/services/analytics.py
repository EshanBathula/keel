"""Core financial analytics: monthly series, KPIs, and the Keel health score."""
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Transaction, Invoice, TxType, InvoiceStatus
from ..money import to_dollars


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def shift_month(key: str, delta: int) -> str:
    y, m = map(int, key.split("-"))
    total = y * 12 + (m - 1) + delta
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def monthly_series_cents(db: Session, user_id: int, months: int = 12, today: date | None = None) -> list[dict]:
    """Revenue/expenses/net in integer cents per trailing month — the arithmetic-safe core.

    Summing many transactions as cents (ints) avoids the binary-float drift that
    summing dollar floats would accumulate.
    """
    today = today or date.today()
    current = month_key(today)
    keys = [shift_month(current, -(months - 1 - i)) for i in range(months)]

    rev: dict[str, int] = defaultdict(int)
    exp: dict[str, int] = defaultdict(int)
    txs = db.scalars(select(Transaction).where(Transaction.user_id == user_id)).all()
    for tx in txs:
        k = month_key(tx.date)
        if tx.type == TxType.income:
            rev[k] += tx.amount_cents
        else:
            exp[k] += tx.amount_cents

    return [
        {"month": k, "revenue_cents": rev[k], "expenses_cents": exp[k], "net_cents": rev[k] - exp[k]}
        for k in keys
    ]


def monthly_series(db: Session, user_id: int, months: int = 12, today: date | None = None) -> list[dict]:
    """Dollar-denominated monthly series for API responses."""
    return [
        {"month": p["month"], "revenue": to_dollars(p["revenue_cents"]),
         "expenses": to_dollars(p["expenses_cents"]), "net": to_dollars(p["net_cents"])}
        for p in monthly_series_cents(db, user_id, months=months, today=today)
    ]


def avg_monthly_burn_cents(db: Session, user_id: int, today: date | None = None) -> int:
    """Average monthly expenses over the trailing 6 complete-ish months with activity."""
    series = monthly_series_cents(db, user_id, months=12, today=today)
    active = [p for p in series[-6:] if p["revenue_cents"] or p["expenses_cents"]]
    return round(sum(p["expenses_cents"] for p in active) / len(active)) if active else 0


def approx_cash_balance_cents(db: Session, user_id: int, today: date | None = None) -> int:
    """Proxy for current cash on hand: cumulative net income over the trailing
    12 months. Keel has no bank-feed integration, so this is a computed proxy,
    not a real balance — used consistently for both cash-runway (below) and
    the forecast's starting cash-curve balance (services/forecast).
    """
    series = monthly_series_cents(db, user_id, months=12, today=today)
    return sum(p["net_cents"] for p in series)


def compute_kpis(db: Session, user_id: int, today: date | None = None) -> dict:
    today = today or date.today()
    series = monthly_series_cents(db, user_id, months=12, today=today)
    this_m, last_m = series[-1], series[-2]

    growth = None
    if last_m["revenue_cents"] > 0:
        growth = round((this_m["revenue_cents"] - last_m["revenue_cents"]) / last_m["revenue_cents"] * 100, 1)

    margin = None
    if this_m["revenue_cents"] > 0:
        margin = round(this_m["net_cents"] / this_m["revenue_cents"] * 100, 1)

    avg_burn_cents = avg_monthly_burn_cents(db, user_id, today=today)

    # Runway: cumulative net (proxy for cash) / burn.
    cash_cents = approx_cash_balance_cents(db, user_id, today=today)
    runway = round(max(cash_cents, 0) / avg_burn_cents, 1) if avg_burn_cents > 0 else None

    invoices = db.scalars(select(Invoice).where(Invoice.user_id == user_id)).all()
    outstanding_cents = sum(
        i.amount_cents for i in invoices if i.status in (InvoiceStatus.sent, InvoiceStatus.overdue))
    overdue_cents = sum(
        i.amount_cents for i in invoices
        if i.status == InvoiceStatus.overdue or (i.status == InvoiceStatus.sent and i.due_date < today)
    )

    score, grade = health_score(series, margin, growth, outstanding_cents, overdue_cents, runway)

    return {
        "revenue_this_month": to_dollars(this_m["revenue_cents"]),
        "revenue_last_month": to_dollars(last_m["revenue_cents"]),
        "revenue_growth_pct": growth,
        "expenses_this_month": to_dollars(this_m["expenses_cents"]),
        "net_this_month": to_dollars(this_m["net_cents"]),
        "profit_margin_pct": margin,
        "avg_monthly_burn": to_dollars(avg_burn_cents),
        "cash_runway_months": runway,
        "outstanding_receivables": to_dollars(outstanding_cents),
        "overdue_receivables": to_dollars(overdue_cents),
        "health_score": score,
        "health_grade": grade,
    }


def health_score(series, margin, growth, outstanding_cents, overdue_cents, runway) -> tuple[int, str]:
    """Composite 0-100 score across profitability, growth, collections, and runway."""
    score = 50.0

    # Profitability (up to ±25)
    if margin is not None:
        score += max(min(margin, 50), -50) * 0.5

    # Growth trend (up to ±15)
    if growth is not None:
        score += max(min(growth, 30), -30) * 0.5

    # Consistency: how many of the last 6 months were profitable (up to +10)
    recent = [p for p in series[-6:] if p["revenue_cents"] or p["expenses_cents"]]
    if recent:
        score += (sum(1 for p in recent if p["net_cents"] > 0) / len(recent)) * 10

    # Collections: overdue receivables as share of outstanding (up to -10)
    if outstanding_cents > 0:
        score -= (overdue_cents / outstanding_cents) * 10

    # Runway (up to ±10)
    if runway is not None:
        if runway >= 6:
            score += 10
        elif runway < 2:
            score -= 10

    score_int = int(max(0, min(100, round(score))))
    grade = ("A" if score_int >= 85 else "B" if score_int >= 70 else
             "C" if score_int >= 55 else "D" if score_int >= 40 else "F")
    return score_int, grade


def category_breakdown(db: Session, user_id: int, tx_type: TxType, months: int = 12,
                       today: date | None = None) -> list[dict]:
    today = today or date.today()
    cutoff_key = shift_month(month_key(today), -(months - 1))
    totals: dict[str, int] = defaultdict(int)
    txs = db.scalars(select(Transaction).where(
        Transaction.user_id == user_id, Transaction.type == tx_type)).all()
    for tx in txs:
        if month_key(tx.date) >= cutoff_key:
            totals[tx.category] += tx.amount_cents
    return sorted(
        [{"category": c, "total": to_dollars(v)} for c, v in totals.items()],
        key=lambda x: -x["total"],
    )


def top_customers(db: Session, user_id: int, limit: int = 5) -> list[dict]:
    totals: dict[int, int] = defaultdict(int)
    names: dict[int, str] = {}
    txs = db.scalars(select(Transaction).where(
        Transaction.user_id == user_id, Transaction.type == TxType.income)).all()
    for tx in txs:
        if tx.customer_id and tx.customer:
            totals[tx.customer_id] += tx.amount_cents
            names[tx.customer_id] = tx.customer.name
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])[:limit]
    grand_cents = sum(totals.values()) or 1
    return [
        {"customer_id": cid, "name": names[cid], "revenue": to_dollars(v),
         "share_pct": round(v / grand_cents * 100, 1)}
        for cid, v in ranked
    ]
