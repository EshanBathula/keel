"""Shared fixtures for API-level tests."""
import os
from datetime import date

os.environ["DATABASE_URL"] = "sqlite:///./test_keel.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine
from app.rate_limit import login_limiter, register_limiter


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    login_limiter.reset()
    register_limiter.reset()
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
