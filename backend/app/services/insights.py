"""Insight engine: rule-based recommendations to protect margin and grow revenue.

Each rule inspects the user's data and may emit an Insight. Rules are ordered
by severity so the most actionable items surface first. Every number in
insight copy is computed from the user's own data — no canned industry
statistics (see docs/DECISIONS.md, Task 6).
"""
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .analytics import monthly_series, compute_kpis, category_breakdown, top_customers, month_key, shift_month
from .forecast import forecast as run_forecast
from ..models import Customer, Invoice, InvoiceStatus, Transaction, TxType
from ..money import to_dollars

# Chronic late payer: at least this many paid invoices with a recorded
# paid_date, averaging at least this many days past due.
LATE_PAYER_MIN_INVOICES = 2
LATE_PAYER_MIN_AVG_DAYS = 7

# Category trend: quarter-over-quarter growth above this, with at least this
# much spend in the current quarter (so tiny categories don't cry wolf).
QOQ_GROWTH_THRESHOLD_PCT = 25
QOQ_MIN_QUARTER_SPEND_CENTS = 50_000  # $500


def _fmt(n: float) -> str:
    return f"${n:,.0f}"


def _fmt_week(d: date) -> str:
    return f"the week of {d.strftime('%b')} {d.day}"


def _late_payers(db: Session, user_id: int) -> list[dict]:
    """Customers averaging >= LATE_PAYER_MIN_AVG_DAYS past due across at least
    LATE_PAYER_MIN_INVOICES paid invoices with a recorded paid_date."""
    invoices = db.scalars(select(Invoice).where(
        Invoice.user_id == user_id,
        Invoice.paid_date.isnot(None),
        Invoice.customer_id.isnot(None),
    )).all()
    days_by_customer: dict[int, list[int]] = defaultdict(list)
    for inv in invoices:
        days_by_customer[inv.customer_id].append((inv.paid_date - inv.due_date).days)

    flagged = []
    for cid, days in days_by_customer.items():
        avg = sum(days) / len(days)
        if len(days) >= LATE_PAYER_MIN_INVOICES and avg >= LATE_PAYER_MIN_AVG_DAYS:
            customer = db.get(Customer, cid)
            outstanding_cents = sum(
                i.amount_cents for i in customer.invoices
                if i.status in (InvoiceStatus.sent, InvoiceStatus.overdue)
            )
            flagged.append({
                "name": customer.name, "avg_days_late": round(avg),
                "n_invoices": len(days), "outstanding_cents": outstanding_cents,
            })
    return sorted(flagged, key=lambda f: -f["avg_days_late"])


def _category_qoq_growth(db: Session, user_id: int, today: date) -> list[dict]:
    """Expense categories growing >= QOQ_GROWTH_THRESHOLD_PCT over the last
    three COMPLETE months vs. the three before — complete months so the
    current partial month can't fake a decline or mute a rise."""
    current = month_key(today)
    cur_months = {shift_month(current, -k) for k in (1, 2, 3)}
    prev_months = {shift_month(current, -k) for k in (4, 5, 6)}

    cur: dict[str, int] = defaultdict(int)
    prev: dict[str, int] = defaultdict(int)
    txs = db.scalars(select(Transaction).where(
        Transaction.user_id == user_id, Transaction.type == TxType.expense)).all()
    for tx in txs:
        mk = month_key(tx.date)
        if mk in cur_months:
            cur[tx.category] += tx.amount_cents
        elif mk in prev_months:
            prev[tx.category] += tx.amount_cents

    growing = []
    for cat, cur_cents in cur.items():
        prev_cents = prev.get(cat, 0)
        if prev_cents <= 0 or cur_cents < QOQ_MIN_QUARTER_SPEND_CENTS:
            continue
        growth_pct = (cur_cents - prev_cents) / prev_cents * 100
        if growth_pct >= QOQ_GROWTH_THRESHOLD_PCT:
            growing.append({
                "category": cat, "growth_pct": round(growth_pct),
                "cur_cents": cur_cents, "prev_cents": prev_cents,
            })
    return sorted(growing, key=lambda g: -(g["cur_cents"] - g["prev_cents"]))


def generate_insights(db: Session, user_id: int, today: date | None = None) -> list[dict]:
    today = today or date.today()
    kpis = compute_kpis(db, user_id, today=today)
    series = monthly_series(db, user_id, months=12, today=today)
    insights: list[dict] = []

    # 1. Overdue receivables — fastest cash win there is.
    if kpis["overdue_receivables"] > 0:
        insights.append({
            "id": "overdue-receivables",
            "severity": "critical",
            "title": "Collect overdue invoices",
            "detail": (
                f"You have {_fmt(kpis['overdue_receivables'])} in overdue receivables. "
                "Send reminders today and consider late fees or shorter payment terms "
                "(e.g. net-15) for repeat offenders. Collections are the cheapest revenue you'll ever earn."
            ),
            "estimated_impact": f"+{_fmt(kpis['overdue_receivables'])} cash recovered",
        })

    # 2. Forecast tie-in: the cash-flow engine's low-cash alert, surfaced
    #    where the owner actually looks. Names the projected date and amount.
    fc = run_forecast(db, user_id, horizon_months=3, today=today)
    alert = fc["cash_low_alert"]
    if alert:
        low_conf = " (Note: limited history makes this forecast rough.)" if fc["confidence"] == "low" else ""
        insights.append({
            "id": "forecast-cash-low",
            "severity": "critical",
            "title": f"Cash projected to run low {_fmt_week(alert['week_start'])}",
            "detail": (
                f"In a pessimistic (1-in-10) scenario from your own cash-flow backtest, cash drops "
                f"{_fmt(alert['shortfall'])} below a one-month expense buffer in {_fmt_week(alert['week_start'])}. "
                f"Collect outstanding invoices and defer discretionary spend before then."
                f"{low_conf}"
            ),
            "estimated_impact": f"{_fmt(alert['shortfall'])} shortfall vs. buffer",
        })

    # 3. Runway pressure.
    runway = kpis["cash_runway_months"]
    if runway is not None and runway < 3:
        insights.append({
            "id": "short-runway",
            "severity": "critical",
            "title": f"Runway is roughly {runway} months",
            "detail": (
                "At the current burn rate, reserves cover less than a quarter. Prioritize "
                "invoicing outstanding work, defer non-essential spend, and review the top "
                "expense categories below for cuts."
            ),
        })

    # 4. Payment behavior: chronic late payers, with their actual averages
    #    computed from paid_date history.
    late = _late_payers(db, user_id)
    if late:
        worst = late[0]
        exposure_cents = sum(f["outstanding_cents"] for f in late)
        if len(late) == 1:
            title = f"{worst['name']} pays {worst['avg_days_late']} days late on average"
        else:
            title = f"{len(late)} customers routinely pay late"
        breakdown = "; ".join(
            f"{f['name']} averages {f['avg_days_late']} days past due across {f['n_invoices']} invoices"
            for f in late[:3]
        )
        insights.append({
            "id": "late-payers",
            "severity": "warning",
            "title": title,
            "detail": (
                f"{breakdown}. Send reminders before the due date, and consider shorter terms "
                "(net-15), deposits, or late fees for these customers specifically."
            ),
            "estimated_impact": (
                f"{_fmt(to_dollars(exposure_cents))} currently outstanding with late payers"
                if exposure_cents else None
            ),
        })

    # 5. Revenue concentration risk.
    top = top_customers(db, user_id, limit=1)
    if top and top[0]["share_pct"] >= 40:
        c = top[0]
        insights.append({
            "id": "revenue-concentration",
            "severity": "warning",
            "title": f"{c['name']} is {c['share_pct']}% of revenue",
            "detail": (
                "Losing this customer would be a major shock. Diversify by reinvesting in the "
                "channel that acquired your next-best customers, and consider a multi-period "
                "contract to lock in this relationship."
            ),
        })

    # 4. Expense spike detection (this month vs trailing average per category).
    exp_now = {c["category"]: c["total"] for c in category_breakdown(db, user_id, TxType.expense, months=1, today=today)}
    exp_hist = {c["category"]: c["total"] for c in category_breakdown(db, user_id, TxType.expense, months=6, today=today)}
    for cat, now in exp_now.items():
        hist_avg = (exp_hist.get(cat, 0) - now) / 5 if exp_hist.get(cat, 0) > now else 0
        if hist_avg > 0 and now > hist_avg * 1.6 and now - hist_avg > 200:
            insights.append({
                "id": f"expense-spike-{cat.lower().replace(' ', '-')}",
                "severity": "warning",
                "title": f"{cat} spend is {round(now / hist_avg, 1)}x its usual level",
                "detail": (
                    f"{cat} hit {_fmt(now)} this month against a ~{_fmt(hist_avg)} monthly average. "
                    "Verify it's intentional; recurring creep in this category compounds fast."
                ),
                "estimated_impact": f"-{_fmt(now - hist_avg)}/mo if reverted",
            })

    # 7. Category trend: sustained quarter-over-quarter growth (complete
    #    months), distinct from the single-month spike rule above.
    for g in _category_qoq_growth(db, user_id, today)[:2]:
        delta = to_dollars(g["cur_cents"] - g["prev_cents"])
        insights.append({
            "id": f"category-trend-{g['category'].lower().replace(' ', '-')}",
            "severity": "warning",
            "title": f"{g['category']} spending is up {g['growth_pct']}% quarter over quarter",
            "detail": (
                f"{g['category']} totaled {_fmt(to_dollars(g['cur_cents']))} over the last three "
                f"complete months vs {_fmt(to_dollars(g['prev_cents']))} the three before — a "
                f"{_fmt(delta)} increase. A one-month spike is noise; a quarter is a trend. "
                "Check whether this growth is buying you anything."
            ),
            "estimated_impact": f"-{_fmt(delta)}/quarter if reverted",
        })

    # 8. Margin improvement via pricing.
    margin = kpis["profit_margin_pct"]
    if margin is not None and 0 < margin < 15:
        rev = kpis["revenue_this_month"]
        insights.append({
            "id": "thin-margin-pricing",
            "severity": "opportunity",
            "title": f"Profit margin is thin at {margin}%",
            "detail": (
                f"On {_fmt(rev)} of monthly revenue, a 5% price increase adds ~{_fmt(rev * 0.05)} "
                "straight to profit if volume holds. Test it on new customers first and watch "
                "whether close rates actually move."
            ),
            "estimated_impact": f"+{_fmt(rev * 0.05)}/mo profit",
        })

    # 6. Declining revenue trend.
    recent = [p["revenue"] for p in series[-3:]]
    if len(recent) == 3 and recent[0] > recent[1] > recent[2] and recent[0] > 0:
        drop = round((recent[0] - recent[2]) / recent[0] * 100, 1)
        insights.append({
            "id": "revenue-decline",
            "severity": "warning",
            "title": f"Revenue has fallen {drop}% over three months",
            "detail": (
                "Two consecutive down months is a trend, not noise. Re-engage lapsed customers "
                "(a win-back email to anyone inactive 60+ days is the highest-ROI first move) and "
                "review whether a top customer's volume changed."
            ),
        })

    # 7. Growth acknowledgement — reinforce what's working.
    growth = kpis["revenue_growth_pct"]
    if growth is not None and growth >= 10:
        insights.append({
            "id": "growth-momentum",
            "severity": "positive",
            "title": f"Revenue grew {growth}% month over month",
            "detail": (
                "Momentum is real. Identify which customer segment or channel drove the increase "
                "and double the budget or time you allocate to it while the trend holds."
            ),
        })

    # 8. Idle customers with purchase history.
    customers = top_customers(db, user_id, limit=10)
    if len(customers) >= 3:
        insights.append({
            "id": "upsell-top-customers",
            "severity": "opportunity",
            "title": "Your top customers are your best growth channel",
            "detail": (
                f"Your top three customers ({', '.join(c['name'] for c in customers[:3])}) already "
                "trust you. A structured quarterly check-in with an expansion offer costs a "
                "conversation — new-customer acquisition costs marketing spend and a sales cycle."
            ),
        })

    order = {"critical": 0, "warning": 1, "opportunity": 2, "positive": 3}
    insights.sort(key=lambda i: order.get(i["severity"], 9))
    return insights
