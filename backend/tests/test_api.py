"""End-to-end API tests against an in-memory SQLite database."""
import os
import sys
from datetime import date, timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_keel.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth(client):
    r = client.post("/api/auth/register", json={
        "email": "owner@example.com", "password": "supersecret1", "business_name": "Test Co"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def month_str(offset: int) -> str:
    d = date.today()
    total = d.year * 12 + (d.month - 1) + offset
    return f"{total // 12:04d}-{total % 12 + 1:02d}-15"


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
    assert client.get("/api/transactions", headers=other).json() == []
    assert client.delete(f"/api/transactions/{tx_id}", headers=other).status_code == 404

    assert len(client.get("/api/transactions", headers=auth).json()) == 1
    assert client.delete(f"/api/transactions/{tx_id}", headers=auth).status_code == 204
    assert client.get("/api/transactions", headers=auth).json() == []


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


def test_forecast_shape(client, auth):
    for offset in range(-5, 1):
        client.post("/api/transactions", headers=auth, json={
            "type": "income", "amount": 1000 + (offset + 5) * 100, "category": "Sales",
            "date": month_str(offset)})
    f = client.get("/api/analytics/forecast?horizon=4", headers=auth).json()
    assert len(f) == 4
    for p in f:
        assert p["lower"] <= p["projected_revenue"] <= p["upper"]
        assert p["projected_revenue"] >= 0


def test_invoice_paid_creates_income(client, auth):
    c = client.post("/api/customers", headers=auth, json={"name": "Acme"}).json()
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": c["id"], "number": "INV-1", "amount": 750,
        "status": "sent", "issue_date": str(date.today() - timedelta(days=10)),
        "due_date": str(date.today() + timedelta(days=20))}).json()
    r = client.patch(f"/api/invoices/{inv['id']}", headers=auth, json={"status": "paid"})
    assert r.status_code == 200
    txs = client.get("/api/transactions", headers=auth).json()
    assert any(t["amount"] == 750 and t["type"] == "income" for t in txs)


def test_overdue_autoflag_and_insights(client, auth):
    client.post("/api/invoices", headers=auth, json={
        "number": "INV-9", "amount": 999, "status": "sent",
        "issue_date": str(date.today() - timedelta(days=45)),
        "due_date": str(date.today() - timedelta(days=15))})
    invoices = client.get("/api/invoices", headers=auth).json()
    assert invoices[0]["status"] == "overdue"
    ins = client.get("/api/analytics/insights", headers=auth).json()
    assert any(i["id"] == "overdue-receivables" and i["severity"] == "critical" for i in ins)
