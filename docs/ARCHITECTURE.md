# Architecture

```
┌──────────────────────┐        /api proxy        ┌──────────────────────────┐
│  React SPA (Vite)    │ ───────────────────────▶ │  FastAPI                 │
│  Dashboard, Insights │                          │  routers/ → services/    │
│  Forecast, Ledger UI │ ◀─────────────────────── │  SQLAlchemy ORM          │
└──────────────────────┘        JSON + JWT        └───────────┬──────────────┘
                                                              │
                                                       ┌──────▼──────┐
                                                       │  SQLite /   │
                                                       │  PostgreSQL │
                                                       └─────────────┘
```

## Backend layout

```
backend/app/
├── main.py          FastAPI app assembly, CORS, table creation
├── config.py        Pydantic settings (env-overridable)
├── database.py      Engine/session, declarative base
├── auth.py          PBKDF2 hashing, JWT issue/verify, current-user dependency
├── models.py        User, Customer, Transaction, Invoice
├── schemas.py       Request/response models
├── seed.py          Demo data generator (12 months, realistic seasonality)
├── routers/         Thin HTTP layer — validation + auth, no business logic
└── services/        All business logic, unit-testable without HTTP
    ├── analytics.py   Monthly series, KPIs, health score, breakdowns
    ├── forecast.py    OLS trend + moving-average blend, confidence bands
    └── insights.py    Rule engine producing prioritized recommendations
```

**Design decisions**

- **Routers stay thin; services own logic.** Every analytic accepts a `Session` and
  `user_id`, so it can be tested or reused (CLI, background jobs) without FastAPI.
- **Amounts are stored positive**; the `type` column determines sign. This keeps
  aggregation code simple and prevents sign-error bugs.
- **Auth has zero heavyweight dependencies** — PBKDF2 from the standard library plus
  PyJWT. Swappable for OAuth later without touching routers (only the dependency).
- **SQLite by default, PostgreSQL by env var.** The ORM layer is dialect-agnostic;
  set `DATABASE_URL` and deploy.
- **Invoices drive revenue.** Marking an invoice paid emits an income transaction,
  so receivables and the P&L can never drift apart.

## The health score

A 0–100 composite starting from 50 and adjusted by:

| Factor | Weight | Signal |
|--------|--------|--------|
| Profit margin (this month) | ±25 | Is the business making money? |
| MoM revenue growth | ±15 | Which direction is it heading? |
| Profitable months (last 6) | +10 | Consistency, not just a good month |
| Overdue share of receivables | −10 | Collections discipline |
| Cash runway | ±10 | ≥6 months is safe, <2 is danger |

## The forecaster

1. Fit ordinary least squares to the trailing 12 months (leading empty months dropped
   so young businesses aren't dragged toward zero).
2. Blend the trend 60/40 with the 3-month moving average to damp overreaction.
3. Clamp at zero (revenue/expenses can't go negative).
4. Band = 1.28 × residual std deviation (~80% interval), widening 15% per month of
   horizon to reflect growing uncertainty.

Pure Python by design — no NumPy — to keep the install footprint minimal.

## The insight engine

Each rule in `services/insights.py` is an independent function of the user's data that
may emit one insight with a severity (`critical` → `warning` → `opportunity` →
`positive`) and, where computable, an estimated dollar impact. Adding a rule is
appending one block — no framework. Current rules: overdue collections, runway
pressure, revenue concentration, per-category expense spikes, thin-margin pricing,
three-month decline, growth momentum, and top-customer upsell.

## Frontend

Plain React + fetch (no state-management framework needed at this size). `lib/api.js`
centralizes the JWT header, 401 → login redirect, and money/date formatting. Charts
are Recharts. The design system lives in `styles.css` as CSS custom properties.
