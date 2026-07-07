"""Tests for the computed insight rules added in Task 6: payment behavior,
category QoQ trends, and the forecast cash-low tie-in."""
from datetime import date, timedelta

from tests.conftest import month_str
from app.services.weekly import week_start


def get_insights(client, auth):
    r = client.get("/api/analytics/insights", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def by_id(insights, insight_id):
    return next((i for i in insights if i["id"] == insight_id), None)


def test_late_payer_insight_reports_actual_average(client, auth):
    c = client.post("/api/customers", headers=auth, json={"name": "SlowPay LLC"}).json()

    # Two invoices, both due 20 days ago, paid today -> each 20 days late.
    for n in (1, 2):
        inv = client.post("/api/invoices", headers=auth, json={
            "customer_id": c["id"], "number": f"INV-L{n}", "amount": 400, "status": "sent",
            "issue_date": str(date.today() - timedelta(days=50)),
            "due_date": str(date.today() - timedelta(days=20))}).json()
        client.patch(f"/api/invoices/{inv['id']}", headers=auth, json={"status": "paid"})

    # One still outstanding, so the exposure figure has something to count.
    client.post("/api/invoices", headers=auth, json={
        "customer_id": c["id"], "number": "INV-L3", "amount": 750, "status": "sent",
        "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=30))})

    ins = by_id(get_insights(client, auth), "late-payers")
    assert ins is not None
    assert ins["severity"] == "warning"
    assert "SlowPay LLC" in ins["title"]
    assert "20 days late" in ins["title"]
    assert "2 invoices" in ins["detail"]
    assert "$750" in ins["estimated_impact"]


def test_on_time_customer_not_flagged(client, auth):
    c = client.post("/api/customers", headers=auth, json={"name": "Prompt Co"}).json()
    for n in (1, 2):
        inv = client.post("/api/invoices", headers=auth, json={
            "customer_id": c["id"], "number": f"INV-P{n}", "amount": 400, "status": "sent",
            "issue_date": str(date.today() - timedelta(days=10)),
            "due_date": str(date.today() + timedelta(days=20))}).json()
        client.patch(f"/api/invoices/{inv['id']}", headers=auth, json={"status": "paid"})
    assert by_id(get_insights(client, auth), "late-payers") is None


def test_single_late_invoice_not_flagged(client, auth):
    # One late invoice is an anecdote, not a pattern (threshold is 2+).
    c = client.post("/api/customers", headers=auth, json={"name": "OneOff Inc"}).json()
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": c["id"], "number": "INV-O1", "amount": 400, "status": "sent",
        "issue_date": str(date.today() - timedelta(days=40)),
        "due_date": str(date.today() - timedelta(days=15))}).json()
    client.patch(f"/api/invoices/{inv['id']}", headers=auth, json={"status": "paid"})
    assert by_id(get_insights(client, auth), "late-payers") is None


def test_category_qoq_trend_computed_numbers(client, auth):
    # Marketing: $1,000/mo in months -6..-4, $1,500/mo in months -3..-1
    # -> $3,000 -> $4,500 = +50%. Rent stays flat and must not fire.
    for offset in (-6, -5, -4):
        client.post("/api/transactions", headers=auth, json={
            "type": "expense", "amount": 1000, "category": "Marketing", "date": month_str(offset)})
        client.post("/api/transactions", headers=auth, json={
            "type": "expense", "amount": 2000, "category": "Rent", "date": month_str(offset)})
    for offset in (-3, -2, -1):
        client.post("/api/transactions", headers=auth, json={
            "type": "expense", "amount": 1500, "category": "Marketing", "date": month_str(offset)})
        client.post("/api/transactions", headers=auth, json={
            "type": "expense", "amount": 2000, "category": "Rent", "date": month_str(offset)})

    insights = get_insights(client, auth)
    ins = by_id(insights, "category-trend-marketing")
    assert ins is not None
    assert "50%" in ins["title"]
    assert "$4,500" in ins["detail"] and "$3,000" in ins["detail"]
    assert "$1,500" in ins["estimated_impact"]
    assert by_id(insights, "category-trend-rent") is None


def test_small_category_growth_not_flagged(client, auth):
    # 100% growth but only $200/quarter — under the $500 floor, stays quiet.
    for offset in (-6, -5, -4):
        client.post("/api/transactions", headers=auth, json={
            "type": "expense", "amount": 33, "category": "Snacks", "date": month_str(offset)})
    for offset in (-3, -2, -1):
        client.post("/api/transactions", headers=auth, json={
            "type": "expense", "amount": 66, "category": "Snacks", "date": month_str(offset)})
    assert by_id(get_insights(client, auth), "category-trend-snacks") is None


def test_forecast_cash_low_emits_critical_insight(client, auth):
    # Heavy steady burn (same shape as the engine's alert test): the forecast
    # cash_low_alert must surface as a critical insight naming date + amount.
    monday = week_start(date.today())
    for w in range(1, 17):
        d = str(monday - timedelta(weeks=w))
        client.post("/api/transactions", headers=auth, json={
            "type": "income", "amount": 100, "category": "Services", "date": d})
        client.post("/api/transactions", headers=auth, json={
            "type": "expense", "amount": 1500, "category": "Ops", "date": d})

    ins = by_id(get_insights(client, auth), "forecast-cash-low")
    assert ins is not None
    assert ins["severity"] == "critical"
    assert "the week of" in ins["title"]
    assert "$" in ins["detail"]
    assert "shortfall" in ins["estimated_impact"]


def test_healthy_business_no_cash_low_insight(client, auth):
    monday = week_start(date.today())
    for w in range(1, 17):
        d = str(monday - timedelta(weeks=w))
        client.post("/api/transactions", headers=auth, json={
            "type": "income", "amount": 2000, "category": "Services", "date": d})
        client.post("/api/transactions", headers=auth, json={
            "type": "expense", "amount": 500, "category": "Ops", "date": d})
    assert by_id(get_insights(client, auth), "forecast-cash-low") is None
