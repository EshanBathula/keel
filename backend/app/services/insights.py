"""Insight engine: rule-based recommendations to protect margin and grow revenue.

Each rule inspects the user's data and may emit an Insight. Rules are ordered
by severity so the most actionable items surface first.
"""
from datetime import date

from sqlalchemy.orm import Session

from .analytics import monthly_series, compute_kpis, category_breakdown, top_customers
from ..models import TxType


def _fmt(n: float) -> str:
    return f"${n:,.0f}"


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

    # 2. Runway pressure.
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

    # 3. Revenue concentration risk.
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

    # 5. Margin improvement via pricing.
    margin = kpis["profit_margin_pct"]
    if margin is not None and 0 < margin < 15:
        rev = kpis["revenue_this_month"]
        insights.append({
            "id": "thin-margin-pricing",
            "severity": "opportunity",
            "title": f"Profit margin is thin at {margin}%",
            "detail": (
                "A 5% price increase typically loses far fewer customers than it earns in margin. "
                f"On {_fmt(rev)} of monthly revenue, +5% pricing adds ~{_fmt(rev * 0.05)} straight "
                "to profit. Test it on new customers first."
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
                "trust you. A structured quarterly check-in with an expansion offer converts far "
                "better than new-customer acquisition — typically 60-70% vs 5-20%."
            ),
        })

    order = {"critical": 0, "warning": 1, "opportunity": 2, "positive": 3}
    insights.sort(key=lambda i: order.get(i["severity"], 9))
    return insights
