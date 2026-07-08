"""Keel API — financial intelligence for small business."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .logging_config import configure_logging
from .routers import analytics, auth, customers, invoices, transactions

# Schema is managed by Alembic (`alembic upgrade head`), not create_all() —
# see docs/DECISIONS.md. Tests are the one exception (Base.metadata.create_all
# directly, for speed and isolation).

configure_logging(settings.log_level)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Keel API starting", extra={"env": settings.env})
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Track cash, score financial health, forecast cash flow, and act on revenue insights.",
    lifespan=lifespan,
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
