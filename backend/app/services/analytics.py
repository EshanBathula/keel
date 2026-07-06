"""Core financial analytics: monthly series, KPIs, and the Keel health score."""
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Transaction, Invoice, TxType, InvoiceStatus


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def shift_month(key: str, delta: int) -> str:
    y, m = map(int, key.split("-"))
    total = y * 12 + (m - 1) + delta
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def monthly_series(db: Session, user_id: int, months: int = 12, today: date | None = None) -> list[dict]:
    """Revenue/expenses/net per month for the trailing `months` months (inclusive of current)."""
    today = today or date.today()
    current = month_key(today)
    keys = [shift_month(current, -(months - 1 - i)) for i in range(months)]

    rev: dict[str, float] = defaultdict(float)
    exp: dict[str, float] = defaultdict(float)
    txs = db.scalars(select(Transaction).where(Transaction.user_id == user_id)).all()
    for tx in txs:
        k = month_key(tx.date)
        if tx.type == TxType.income:
            rev[k] += tx.amount
        else:
            exp[k] += tx.amount

    return [
        {"month": k, "revenue": round(rev[k], 2), "expenses": round(exp[k], 2), "net": round(rev[k] - exp[k], 2)}
        for k in keys
    ]


def compute_kpis(db: Session, user_id: int, today: date | None = None) -> dict:
    today = today or date.today()
    series = monthly_series(db, user_id, months=12, today=today)
    this_m, last_m = series[-1], series[-2]

    growth = None
    if last_m["revenue"] > 0:
        growth = round((this_m["revenue"] - last_m["revenue"]) / last_m["revenue"] * 100, 1)

    margin = None
    if this_m["revenue"] > 0:
        margin = round(this_m["net"] / this_m["revenue"] * 100, 1)

    # Burn: average monthly expenses over trailing 6 complete-ish months with activity.
    active = [p for p in series[-6:] if p["revenue"] or p["expenses"]]
    avg_burn = round(sum(p["expenses"] for p in active) / len(active), 2) if active else 0.0

    # Runway: cumulative net (proxy for cash) / burn.
    cash = sum(p["net"] for p in series)
    runway = round(max(cash, 0) / avg_burn, 1) if avg_burn > 0 else None

    invoices = db.scalars(select(Invoice).where(Invoice.user_id == user_id)).all()
    outstanding = sum(i.amount for i in invoices if i.status in (InvoiceStatus.sent, InvoiceStatus.overdue))
    overdue = sum(
        i.amount for i in invoices
        if i.status == InvoiceStatus.overdue or (i.status == InvoiceStatus.sent and i.due_date < today)
    )

    score, grade = health_score(series, margin, growth, outstanding, overdue, runway)

    return {
        "revenue_this_month": this_m["revenue"],
        "revenue_last_month": last_m["revenue"],
        "revenue_growth_pct": growth,
        "expenses_this_month": this_m["expenses"],
        "net_this_month": this_m["net"],
        "profit_margin_pct": margin,
        "avg_monthly_burn": avg_burn,
        "cash_runway_months": runway,
        "outstanding_receivables": round(outstanding, 2),
        "overdue_receivables": round(overdue, 2),
        "health_score": score,
        "health_grade": grade,
    }


def health_score(series, margin, growth, outstanding, overdue, runway) -> tuple[int, str]:
    """Composite 0-100 score across profitability, growth, collections, and runway."""
    score = 50.0

    # Profitability (up to ±25)
    if margin is not None:
        score += max(min(margin, 50), -50) * 0.5

    # Growth trend (up to ±15)
    if growth is not None:
        score += max(min(growth, 30), -30) * 0.5

    # Consistency: how many of the last 6 months were profitable (up to +10)
    recent = [p for p in series[-6:] if p["revenue"] or p["expenses"]]
    if recent:
        score += (sum(1 for p in recent if p["net"] > 0) / len(recent)) * 10

    # Collections: overdue receivables as share of outstanding (up to -10)
    if outstanding > 0:
        score -= (overdue / outstanding) * 10

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
    totals: dict[str, float] = defaultdict(float)
    txs = db.scalars(select(Transaction).where(
        Transaction.user_id == user_id, Transaction.type == tx_type)).all()
    for tx in txs:
        if month_key(tx.date) >= cutoff_key:
            totals[tx.category] += tx.amount
    return sorted(
        [{"category": c, "total": round(v, 2)} for c, v in totals.items()],
        key=lambda x: -x["total"],
    )


def top_customers(db: Session, user_id: int, limit: int = 5) -> list[dict]:
    totals: dict[int, float] = defaultdict(float)
    names: dict[int, str] = {}
    txs = db.scalars(select(Transaction).where(
        Transaction.user_id == user_id, Transaction.type == TxType.income)).all()
    for tx in txs:
        if tx.customer_id and tx.customer:
            totals[tx.customer_id] += tx.amount
            names[tx.customer_id] = tx.customer.name
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])[:limit]
    grand = sum(totals.values()) or 1
    return [
        {"customer_id": cid, "name": names[cid], "revenue": round(v, 2),
         "share_pct": round(v / grand * 100, 1)}
        for cid, v in ranked
    ]
