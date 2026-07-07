"""End-to-end API tests against an in-memory SQLite database."""
from datetime import date, timedelta

import pytest

from tests.conftest import month_str


def test_register_login_me(client, auth):
    r = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "supersecret1"})
    assert r.status_code == 200
    r = client.get("/api/auth/me", headers=auth)
    assert r.json()["business_name"] == "Test Co"


def test_duplicate_email_rejected(client, auth):
    r = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "supersecret1"})
    assert r.status_code == 409


def test_requires_auth(client):
    assert client.get("/api/transactions").status_code == 401
    assert client.get("/api/analytics/kpis").status_code == 401


def test_transaction_crud_and_isolation(client, auth):
    r = client.post("/api/transactions", headers=auth, json={
        "type": "income", "amount": 1200.5, "category": "Services",
        "description": "Consulting", "date": str(date.today())})
    assert r.status_code == 201
    tx_id = r.json()["id"]

    # A second user cannot see or delete the first user's data.
    r2 = client.post("/api/auth/register", json={"email": "other@example.com", "password": "supersecret1"})
    other = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    other_page = client.get("/api/transactions", headers=other).json()
    assert other_page["items"] == [] and other_page["total"] == 0
    assert client.delete(f"/api/transactions/{tx_id}", headers=other).status_code == 404

    page = client.get("/api/transactions", headers=auth).json()
    assert len(page["items"]) == 1 and page["total"] == 1
    assert client.delete(f"/api/transactions/{tx_id}", headers=auth).status_code == 204
    page = client.get("/api/transactions", headers=auth).json()
    assert page["items"] == [] and page["total"] == 0


def test_transaction_update(client, auth):
    tx = client.post("/api/transactions", headers=auth, json={
        "type": "expense", "amount": 100, "category": "Software",
        "description": "Old", "date": str(date.today())}).json()

    r = client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"amount": 150.25, "category": "Tools"})
    assert r.status_code == 200
    updated = r.json()
    assert updated["amount"] == 150.25
    assert updated["category"] == "Tools"
    # Fields not in the request body are untouched.
    assert updated["description"] == "Old"
    assert updated["type"] == "expense"

    # A second user cannot edit the first user's transaction.
    r2 = client.post("/api/auth/register", json={"email": "editor@example.com", "password": "supersecret1"})
    other = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    assert client.patch(f"/api/transactions/{tx['id']}", headers=other, json={"amount": 1}).status_code == 404


def test_transaction_update_rejects_other_users_customer(client, auth):
    tx = client.post("/api/transactions", headers=auth, json={
        "type": "income", "amount": 100, "category": "Services", "date": str(date.today())}).json()
    r2 = client.post("/api/auth/register", json={"email": "stranger@example.com", "password": "supersecret1"})
    other_auth = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    other_customer = client.post("/api/customers", headers=other_auth, json={"name": "Not Yours"}).json()

    r = client.patch(f"/api/transactions/{tx['id']}", headers=auth,
                     json={"customer_id": other_customer["id"]})
    assert r.status_code == 400

    r = client.post("/api/transactions", headers=auth, json={
        "type": "income", "amount": 50, "category": "Services", "date": str(date.today()),
        "customer_id": other_customer["id"]})
    assert r.status_code == 400


def test_transaction_filters_and_pagination(client, auth):
    for i in range(5):
        client.post("/api/transactions", headers=auth, json={
            "type": "expense", "amount": 10 + i, "category": "Software",
            "description": f"Tool {i}", "date": str(date.today() - timedelta(days=i))})
    client.post("/api/transactions", headers=auth, json={
        "type": "income", "amount": 500, "category": "Services",
        "description": "Client work", "date": str(date.today())})

    page1 = client.get("/api/transactions?limit=2&offset=0", headers=auth).json()
    assert page1["total"] == 6
    assert len(page1["items"]) == 2
    page2 = client.get("/api/transactions?limit=2&offset=2", headers=auth).json()
    assert len(page2["items"]) == 2
    assert {t["id"] for t in page1["items"]}.isdisjoint({t["id"] for t in page2["items"]})

    by_type = client.get("/api/transactions?type=income", headers=auth).json()
    assert by_type["total"] == 1 and by_type["items"][0]["description"] == "Client work"

    by_text = client.get("/api/transactions?q=client", headers=auth).json()
    assert by_text["total"] == 1 and by_text["items"][0]["description"] == "Client work"

    by_range = client.get(
        f"/api/transactions?date_from={date.today() - timedelta(days=1)}&date_to={date.today()}",
        headers=auth).json()
    assert by_range["total"] == 3  # expenses at i=0 (today) and i=1 (yesterday), plus today's income


def test_csv_import(client, auth):
    csv_data = (
        "date,type,amount,category,description\n"
        f"{date.today()},income,500,Services,Job A\n"
        "01/15/2026,expense,120.75,Software,Tools\n"
        "not-a-date,income,50,Misc,bad row\n"
    )
    r = client.post("/api/transactions/import", headers=auth,
                    files={"file": ("data.csv", csv_data, "text/csv")})
    assert r.status_code == 201
    body = r.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


def test_kpis_and_monthly(client, auth):
    for offset, rev, exp in [(-2, 1000, 600), (-1, 1500, 700), (0, 2000, 800)]:
        client.post("/api/transactions", headers=auth, json={
            "type": "income", "amount": rev, "category": "Sales", "date": month_str(offset)})
        client.post("/api/transactions", headers=auth, json={
            "type": "expense", "amount": exp, "category": "Ops", "date": month_str(offset)})
    k = client.get("/api/analytics/kpis", headers=auth).json()
    assert k["revenue_this_month"] == 2000
    assert k["revenue_last_month"] == 1500
    assert k["revenue_growth_pct"] == pytest.approx(33.3, abs=0.1)
    assert k["net_this_month"] == 1200
    assert 0 <= k["health_score"] <= 100
    monthly = client.get("/api/analytics/monthly?months=3", headers=auth).json()
    assert [p["revenue"] for p in monthly] == [1000, 1500, 2000]


def test_login_rate_limited_after_five_attempts(client, auth):
    for _ in range(5):
        r = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "wrong"})
        assert r.status_code == 401
    r = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "wrong"})
    assert r.status_code == 429


def test_register_rate_limited_after_five_attempts(client):
    for i in range(5):
        r = client.post("/api/auth/register", json={
            "email": f"user{i}@example.com", "password": "supersecret1"})
        assert r.status_code == 201
    r = client.post("/api/auth/register", json={"email": "one-more@example.com", "password": "supersecret1"})
    assert r.status_code == 429


def test_money_sums_without_float_drift(client, auth):
    # 0.10 + 0.20 + 0.30 famously equals 0.6000000000000001 in binary floats.
    # With cents storage the sum must land on exactly 0.6.
    for amt in (0.10, 0.20, 0.30):
        client.post("/api/transactions", headers=auth, json={
            "type": "income", "amount": amt, "category": "Misc", "date": str(date.today())})
    k = client.get("/api/analytics/kpis", headers=auth).json()
    assert k["revenue_this_month"] == 0.6


def test_transaction_amount_rounds_to_nearest_cent(client, auth):
    r = client.post("/api/transactions", headers=auth, json={
        "type": "income", "amount": 19.999999999998, "category": "Services",
        "date": str(date.today())})
    assert r.status_code == 201
    assert r.json()["amount"] == 20.0


def test_invoice_paid_creates_income(client, auth):
    c = client.post("/api/customers", headers=auth, json={"name": "Acme"}).json()
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": c["id"], "number": "INV-1", "amount": 750,
        "status": "sent", "issue_date": str(date.today() - timedelta(days=10)),
        "due_date": str(date.today() + timedelta(days=20))}).json()
    r = client.patch(f"/api/invoices/{inv['id']}", headers=auth, json={"status": "paid"})
    assert r.status_code == 200
    txs = client.get("/api/transactions", headers=auth).json()["items"]
    assert any(t["amount"] == 750 and t["type"] == "income" for t in txs)


def test_invoice_rejects_other_users_customer(client, auth):
    r2 = client.post("/api/auth/register", json={"email": "stranger2@example.com", "password": "supersecret1"})
    other_auth = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    other_customer = client.post("/api/customers", headers=other_auth, json={"name": "Not Yours"}).json()

    r = client.post("/api/invoices", headers=auth, json={
        "customer_id": other_customer["id"], "number": "INV-2", "amount": 500,
        "status": "sent", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=30))})
    assert r.status_code == 400


def test_user_timezone_update_and_validation(client, auth):
    r = client.patch("/api/auth/me", headers=auth, json={"timezone": "not/a/real/zone"})
    assert r.status_code == 422

    r = client.patch("/api/auth/me", headers=auth, json={"timezone": "America/Chicago"})
    assert r.status_code == 200
    assert r.json()["timezone"] == "America/Chicago"

    assert client.get("/api/auth/me", headers=auth).json()["timezone"] == "America/Chicago"


def test_overdue_autoflag_and_insights(client, auth):
    client.post("/api/invoices", headers=auth, json={
        "number": "INV-9", "amount": 999, "status": "sent",
        "issue_date": str(date.today() - timedelta(days=45)),
        "due_date": str(date.today() - timedelta(days=15))})
    invoices = client.get("/api/invoices", headers=auth).json()
    assert invoices[0]["status"] == "overdue"
    ins = client.get("/api/analytics/insights", headers=auth).json()
    assert any(i["id"] == "overdue-receivables" and i["severity"] == "critical" for i in ins)
