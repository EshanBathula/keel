"""Keel API — financial intelligence for small business."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import auth, transactions, customers, invoices, analytics

# Schema is managed by Alembic (`alembic upgrade head`), not create_all() —
# see docs/DECISIONS.md. Tests are the one exception (Base.metadata.create_all
# directly, for speed and isolation).

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Track cash, score financial health, forecast cash flow, and act on revenue insights.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, transactions.router, customers.router, invoices.router, analytics.router):
    app.include_router(r)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}
