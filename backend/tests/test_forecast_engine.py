"""Integration tests for the forecast engine: weekly aggregation, invoice
cash timing, actionable outputs, scenario math, and honesty guards.

These go through the API (like test_api.py) so they exercise the full
router -> engine -> DB path.
"""
from datetime import date, timedelta

import pytest

from app.services.weekly import week_start


def seed_weekly_history(client, auth, weeks=20, revenue=1000.0, expenses=400.0):
    """Steady weekly history ending last week: `revenue` in and `expenses`
    out every week — flat by construction so point forecasts are predictable."""
    monday = week_start(date.today())
    for w in range(1, weeks + 1):
        d = str(monday - timedelta(weeks=w))
        client.post("/api/transactions", headers=auth, json={
            "type": "income", "amount": revenue, "category": "Services", "date": d})
        client.post("/api/transactions", headers=auth, json={
            "type": "expense", "amount": expenses, "category": "Ops", "date": d})


def get_forecast(client, auth, horizon=3):
    r = client.get(f"/api/analytics/forecast?horizon={horizon}", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def test_forecast_response_shape_and_confidence_normal(client, auth):
    seed_weekly_history(client, auth, weeks=20)
    f = get_forecast(client, auth)

    assert f["confidence"] == "normal"
    assert f["caveat"] is None
    assert f["model_revenue"] in ("seasonal_naive", "damped_trend", "ols_ma_blend")
    assert f["expected_error_pct"] is not None and f["expected_error_pct"] >= 0
    assert len(f["monthly"]) >= 3
    assert len(f["weekly"]) >= 12
    for wk in f["weekly"]:
        assert wk["cash_p10"] <= wk["cash_p50"] <= wk["cash_p90"]
    for m in f["monthly"]:
        assert m["lower"] <= m["upper"]
        assert m["projected_revenue"] >= 0 and m["projected_expenses"] >= 0
    # 20 weeks of +600/week net -> healthy positive cash; flat history, positive net.
    assert f["min_cash_balance"] > 0
    assert f["cash_low_alert"] is None
    assert f["safe_to_spend"] > 0


def test_low_confidence_flag_with_sparse_history(client, auth):
    # Only 4 weeks of data — under the 12-week threshold.
    seed_weekly_history(client, auth, weeks=4)
    f = get_forecast(client, auth)
    assert f["confidence"] == "low"
    assert f["caveat"] is not None and "12 weeks" in f["caveat"]


def test_forecast_flat_history_projects_flat_revenue(client, auth):
    # Flat $1000/week -> every candidate model projects ~$1000/week. Monthly
    # buckets hold exactly 4 or 5 whole weeks, so total projected revenue
    # across the horizon must be ~$1000 x number of forecast weeks.
    seed_weekly_history(client, auth, weeks=20, revenue=1000.0, expenses=0.0)
    f = get_forecast(client, auth)
    total = sum(m["projected_revenue"] for m in f["monthly"])
    assert total == pytest.approx(1000 * len(f["weekly"]), rel=0.05)
    # And each 4-5 week month individually lands in the $4k-$5k band.
    for m in f["monthly"]:
        weeks_in_month = sum(1 for w in f["weekly"] if w["week_start"][:7] == m["month"])
        assert m["projected_revenue"] == pytest.approx(1000 * weeks_in_month, rel=0.05)


def test_unpaid_invoice_lands_in_due_week(client, auth):
    seed_weekly_history(client, auth, weeks=20)
    c = client.post("/api/customers", headers=auth, json={"name": "SlowPay Inc"}).json()

    base = get_forecast(client, auth)

    due = date.today() + timedelta(days=30)
    client.post("/api/invoices", headers=auth, json={
        "customer_id": c["id"], "number": "INV-CASH-1", "amount": 5000,
        "status": "sent", "issue_date": str(date.today()), "due_date": str(due)})

    with_invoice = get_forecast(client, auth)

    # The extra expected cash raises the terminal balance vs. baseline...
    assert with_invoice["weekly"][-1]["cash_p50"] > base["weekly"][-1]["cash_p50"]
    # ...and no cash lands before the due week (weeks strictly before the
    # due week must match the baseline).
    due_week = str(week_start(due))
    for b, w in zip(base["weekly"], with_invoice["weekly"]):
        assert b["week_start"] == w["week_start"]
        if w["week_start"] < due_week:
            assert w["cash_p50"] == pytest.approx(b["cash_p50"], abs=1.0)


def test_paid_history_drives_on_time_weighting(client, auth):
    """A customer with a perfect on-time record contributes their whole
    invoice in its due week; the split logic is exercised via invoice
    paid-flow (paid_date is stamped by PATCH)."""
    seed_weekly_history(client, auth, weeks=20)
    c = client.post("/api/customers", headers=auth, json={"name": "Prompt Co"}).json()

    # Build an on-time payment record: due in the future, paid today.
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": c["id"], "number": "INV-H1", "amount": 100, "status": "sent",
        "issue_date": str(date.today() - timedelta(days=10)),
        "due_date": str(date.today() + timedelta(days=5))}).json()
    r = client.patch(f"/api/invoices/{inv['id']}", headers=auth, json={"status": "paid"})
    assert r.json()["paid_date"] == str(date.today())

    base = get_forecast(client, auth)
    due = date.today() + timedelta(days=21)
    client.post("/api/invoices", headers=auth, json={
        "customer_id": c["id"], "number": "INV-H2", "amount": 2600, "status": "sent",
        "issue_date": str(date.today()), "due_date": str(due)})
    f = get_forecast(client, auth)

    # 100% on-time rate -> full 2600 lands in the due week: find that week's
    # cash jump vs. baseline.
    due_week = str(week_start(due))
    jumps = {
        w["week_start"]: round(w["cash_p50"] - b["cash_p50"])
        for b, w in zip(base["weekly"], f["weekly"])
    }
    # Weeks before the due week: no jump. Due week onward: +2600.
    for wk, jump in jumps.items():
        if wk < due_week:
            assert jump == 0
        else:
            assert jump == 2600


def test_scenario_revenue_change_math(client, auth):
    seed_weekly_history(client, auth, weeks=20, revenue=1000.0, expenses=0.0)
    base = get_forecast(client, auth)

    r = client.post("/api/analytics/scenario?horizon=3", headers=auth,
                    json={"monthly_revenue_change_pct": 10})
    assert r.status_code == 200, r.text
    scen = r.json()

    # +10% on organic revenue -> each monthly projected_revenue scales by
    # 1.10 exactly (no invoices exist to dilute the ratio).
    for b, s in zip(base["monthly"], scen["monthly"]):
        assert s["projected_revenue"] == pytest.approx(b["projected_revenue"] * 1.10, rel=0.001)


def test_scenario_new_expense_math(client, auth):
    seed_weekly_history(client, auth, weeks=20)
    base = get_forecast(client, auth)

    # A new $4,000/month expense starting next month.
    start = f"{date.today().year + (date.today().month == 12)}-{(date.today().month % 12) + 1:02d}"
    r = client.post("/api/analytics/scenario?horizon=3", headers=auth,
                    json={"new_monthly_expense_cents": 400000, "start_month": start})
    assert r.status_code == 200, r.text
    scen = r.json()

    base_by_month = {m["month"]: m for m in base["monthly"]}
    for s in scen["monthly"]:
        b = base_by_month[s["month"]]
        added = s["projected_expenses"] - b["projected_expenses"]
        if s["month"] < start:
            assert added == pytest.approx(0, abs=1.0)
        else:
            # Weekly spread = 400000*12/52 cents = $923.08/week; each month
            # holds 4-5 whole weeks (final horizon month may hold fewer).
            weeks_in_month = sum(1 for w in scen["weekly"] if w["week_start"][:7] == s["month"])
            assert added == pytest.approx(923.08 * weeks_in_month, rel=0.01)
    # Scenario terminal cash must be lower than baseline.
    assert scen["weekly"][-1]["cash_p50"] < base["weekly"][-1]["cash_p50"]


def test_scenario_rejects_bad_start_month(client, auth):
    r = client.post("/api/analytics/scenario", headers=auth,
                    json={"new_monthly_expense_cents": 100000, "start_month": "September 2026"})
    assert r.status_code == 422


def test_cash_low_alert_fires_when_burning_down(client, auth):
    # Modest balance, heavy steady burn: revenue 100/wk, expenses 1500/wk.
    # Cumulative net is deeply negative -> alert must fire with a date+amount.
    seed_weekly_history(client, auth, weeks=16, revenue=100.0, expenses=1500.0)
    f = get_forecast(client, auth)
    assert f["cash_low_alert"] is not None
    assert f["cash_low_alert"]["shortfall"] > 0
    assert f["cash_low_alert"]["week_start"] >= str(week_start(date.today()))
    assert f["safe_to_spend"] == 0.0
    assert f["min_cash_balance"] < 0
