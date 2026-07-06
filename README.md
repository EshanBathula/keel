<p align="center">
  <h1 align="center">⚓ Keel</h1>
  <p align="center"><strong>Financial intelligence that keeps your business steady.</strong></p>
  <p align="center">Track cash · Score financial health · Forecast cash flow · Act on revenue insights</p>
</p>

---

Keel is a self-hostable financial intelligence platform for small businesses. It turns your
transactions and invoices into the answers owners actually need: *How healthy is the business?
Where is cash going? What will next quarter look like? What should I do this week to grow revenue?*

## Features

- **Financial health score** — a 0–100 composite of profitability, growth, payment collections,
  and cash runway, rendered as a live "waterline" gauge.
- **KPI dashboard** — revenue, net profit, margin, burn rate, runway, and receivables at a glance,
  with a 12-month revenue vs. expense chart, expense category breakdown, and top-customer ranking.
- **Insight engine** — prioritized, rule-based recommendations with estimated dollar impact:
  overdue-invoice collection, expense-spike detection, revenue-concentration risk, pricing and
  margin opportunities, decline alerts, and upsell plays.
- **Cash-flow forecasting** — OLS trend blended with moving averages, with widening ~80%
  confidence bands, over a 3–12 month horizon.
- **Transactions** — full CRUD plus CSV import (`date,type,amount,category,description`).
- **Invoicing & receivables** — invoices auto-flag as overdue past their due date, and marking
  one paid records the revenue transaction automatically.
- **Multi-tenant auth** — JWT sessions, PBKDF2 password hashing, per-user data isolation
  (covered by tests).

## Stack

| Layer    | Tech |
|----------|------|
| Backend  | Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite (PostgreSQL-ready via `DATABASE_URL`) |
| Frontend | React 18, Vite, Recharts, React Router |
| Auth     | PyJWT + PBKDF2 (no external auth service required) |
| Tests    | pytest, end-to-end against the API |
| Deploy   | Docker / docker-compose, or run each service directly |

## Quick start

### Option A — Docker (one command)

```bash
docker compose up --build
```

The backend container runs `alembic upgrade head` before starting the server,
so the schema is always up to date. Frontend at http://localhost:5173, API
docs at http://localhost:8000/docs.

### Option B — run locally

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head           # create/upgrade the database schema
python -m app.seed             # optional: demo account with 12 months of data
uvicorn app.main:app --reload
```

**Frontend** (second terminal)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Demo login: **demo@keel.app / demopassword** (after seeding).

## Running tests

```bash
cd backend
python -m pytest tests/ -v
```

## Database migrations

Schema changes are managed with [Alembic](https://alembic.sqlalchemy.org/).
`app.main` no longer calls `create_all()` — only the pytest suite does, for
speed and isolation.

```bash
cd backend
alembic upgrade head                       # apply all pending migrations
alembic revision --autogenerate -m "..."   # generate a new migration from model changes
```

`alembic/env.py` reads `DATABASE_URL` from the same app settings as the
server, so it targets whatever database the app is configured to use.

## Configuration

Copy `backend/.env.example` to `backend/.env`:

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `sqlite:///./keel.db` | Any SQLAlchemy URL, e.g. `postgresql+psycopg://...` |
| `JWT_SECRET` | change me | **Set a long random string in production** |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list |

## API overview

Interactive docs live at `/docs` (Swagger) and `/redoc`. Highlights:

```
POST /api/auth/register        Create an account (returns JWT)
POST /api/auth/login           Sign in
GET  /api/analytics/kpis       Health score + core KPIs
GET  /api/analytics/monthly    Revenue/expense/net time series
GET  /api/analytics/forecast   Cash-flow projection with confidence bands
GET  /api/analytics/insights   Prioritized recommendations
POST /api/transactions/import  Bulk CSV import
PATCH /api/invoices/{id}       Update status (paid → auto-records revenue)
```

Full reference in [`docs/API.md`](docs/API.md). Architecture notes in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Roadmap

- [ ] Plaid/bank-feed sync for automatic transaction import
- [ ] Recurring transactions and budget targets per category
- [ ] Scenario planning ("what if I hire in March?") layered on the forecaster
- [ ] Email digests for weekly insights and overdue-invoice reminders
- [ ] Stripe integration for hosted invoice payment
- [ ] Multi-currency support

## License

MIT — see [LICENSE](LICENSE).
