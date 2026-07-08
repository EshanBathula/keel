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
- **Cash-aware forecasting** — a weekly-granularity engine that competes three models (seasonal-
  naive, damped-trend exponential smoothing, OLS+moving-average) per user via rolling-origin
  backtest, layers in known cash from unpaid invoices weighted by each customer's on-time payment
  rate, and reports a backtested error, a low-cash alert, and a "safe to spend today" figure — with
  a plain-language caveat when there's too little history to trust. A scenario planner re-projects
  under hypothetical revenue/expense changes.
- **Insight engine** — prioritized, computed recommendations with real dollar figures: overdue
  collections, a forecast cash-low tie-in, runway pressure, chronic late payers (actual average
  days-to-pay per customer), revenue concentration, expense spikes and quarter-over-quarter
  category trends, pricing opportunities, and growth acknowledgement. No fabricated statistics.
- **Ledger** — full transaction CRUD (with inline editing), date-range and text filtering, and
  server-side pagination; CSV import (`date,type,amount,category,description`). Amounts are stored
  as integer cents throughout, never floats.
- **Invoicing & receivables** — invoices auto-flag as overdue past their due date, and marking one
  paid records the revenue transaction (and payment date, for the forecast/insights above)
  automatically.
- **Multi-tenant auth** — JWT sessions, PBKDF2 password hashing, per-user data isolation, rate-
  limited login/registration, and a production guard against the default JWT secret.
- Per-user timezone for "this month"/"today" boundaries; structured (JSON) logging; error
  boundaries and code-split routes on the frontend.

## Stack

| Layer    | Tech |
|----------|------|
| Backend  | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, SQLite (PostgreSQL-ready via `DATABASE_URL`) |
| Frontend | React 18, Vite, Recharts, React Router |
| Auth     | PyJWT + PBKDF2 (no external auth service required) |
| Tests    | pytest (backend, end-to-end against the API), Vitest + React Testing Library (frontend) |
| Lint     | Ruff (lint + format), enforced in CI |
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

```bash
cd frontend
npm test
```

## Linting

```bash
cd backend
ruff check .            # lint
ruff format --check .   # format check (use `ruff format .` to fix)
```

Both run in CI alongside the test suite.

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
| `ENV` | `development` | Set to `production` to enable production checks (see below) |
| `DATABASE_URL` | `sqlite:///./keel.db` | Any SQLAlchemy URL, e.g. `postgresql+psycopg://...` |
| `JWT_SECRET` | change me | **Set a long random string in production** |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list |
| `LOG_LEVEL` | `INFO` | Python logging level for the app and uvicorn |

With `ENV=production`, the app refuses to start if `JWT_SECRET` is still the
default placeholder value, instead of silently running with a publicly-known
secret. Login and registration are also rate-limited (5/minute and 5/hour per
IP, respectively) to slow down brute-force and signup-spam attempts. Logs
(app and uvicorn access/error) are structured JSON, one object per line.

## API overview

Interactive docs live at `/docs` (Swagger) and `/redoc`. Highlights:

```
POST  /api/auth/register        Create an account (returns JWT)
POST  /api/auth/login           Sign in
PATCH /api/auth/me              Update business name / timezone
GET   /api/analytics/kpis       Health score + core KPIs
GET   /api/analytics/monthly    Revenue/expense/net time series
GET   /api/analytics/forecast   Weekly cash-aware forecast: bands, alerts, safe-to-spend
POST  /api/analytics/scenario   Re-project the forecast under hypothetical changes
GET   /api/analytics/insights   Prioritized, computed recommendations
GET   /api/transactions         Filtered, paginated transaction list
PATCH /api/transactions/{id}    Edit a transaction
POST  /api/transactions/import  Bulk CSV import
PATCH /api/invoices/{id}        Update status (paid → auto-records revenue + paid_date)
```

Full reference in [`docs/API.md`](docs/API.md). Architecture notes in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Roadmap

- [ ] Plaid/bank-feed sync for automatic transaction import (would replace the
      cumulative-net-income proxy currently used for "current cash")
- [ ] Recurring transactions and budget targets per category
- [ ] Email digests for weekly insights and overdue-invoice reminders
- [ ] Stripe integration for hosted invoice payment
- [ ] Multi-currency support
- [ ] httpOnly-cookie auth (current localStorage tokens are documented in
      `docs/DECISIONS.md` as a deliberate, revisitable tradeoff)

## License

MIT — see [LICENSE](LICENSE).
