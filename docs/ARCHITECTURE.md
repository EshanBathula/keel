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
├── main.py          FastAPI app assembly, CORS
├── config.py        Pydantic settings (env-overridable)
├── database.py      Engine/session, declarative base
├── auth.py          PBKDF2 hashing, JWT issue/verify, current-user dependency
├── models.py        User, Customer, Transaction, Invoice
├── money.py         Dollar <-> integer-cents conversion (Decimal-based)
├── schemas.py       Request/response models
├── seed.py          Demo data generator (12 months, realistic seasonality)
├── routers/         Thin HTTP layer — validation + auth, no business logic
└── services/        All business logic, unit-testable without HTTP
    ├── analytics.py   Monthly series, KPIs, health score, breakdowns
    ├── weekly.py      Weekly transaction aggregation (modeling substrate)
    ├── insights.py    Rule engine producing prioritized recommendations
    └── forecast/      Cash-flow forecasting engine (see below)
        ├── models.py    Seasonal-naive, damped-trend, OLS+MA candidates
        ├── backtest.py  Rolling-origin backtest, model selection, error stats
        ├── cash.py      Unpaid-invoice cash overlay (payment-behavior weighted)
        └── engine.py    Orchestration, bands, alerts, scenario planner

backend/alembic/     Schema migrations (see "Database migrations" in README)
```

**Design decisions**

- **Routers stay thin; services own logic.** Every analytic accepts a `Session` and
  `user_id`, so it can be tested or reused (CLI, background jobs) without FastAPI.
- **Amounts are stored positive, as integer cents** (`amount_cents`); the `type`
  column determines sign. Storing cents instead of floats keeps aggregation
  exact; a `.amount` property on the models converts to/from dollars so the
  JSON API is unchanged. See `docs/DECISIONS.md`.
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

## The forecaster (`services/forecast/`)

Weekly-granularity engine with measured model selection and honest uncertainty:

1. **Weekly aggregation** (`weekly.py`): transactions bucketed by Monday-start
   week, complete weeks only (the in-progress week would read as a collapse),
   leading empty weeks trimmed. Organic revenue is tracked separately from
   invoice-payment revenue so known cash isn't modeled twice.
2. **Model competition** (`forecast/models.py`, `forecast/backtest.py`): three
   candidates — seasonal-naive (same week last 52-week cycle), Holt's
   damped-trend exponential smoothing (grid-searched α/β/φ), and the v1
   OLS+moving-average blend — selected per user, per series (revenue and
   expenses independently) by rolling-origin backtest: hold out the last 8
   weeks, walk forward with an expanding window, score 1-step MAE.
3. **Cash-aware overlay** (`forecast/cash.py`): unpaid invoices land on their
   due-date week, split by that customer's historical on-time payment rate,
   with the late share landing at their average historical lateness.
4. **Actionable outputs** (`forecast/engine.py`): projected cash balance per
   week with P10/P50/P90 bands from *empirical* backtest-residual quantiles
   (no normality assumption), widening √h with horizon; minimum balance and
   its date; a `cash_low_alert` when the P10 curve breaches a one-month
   expense buffer; `safe_to_spend` — the largest one-time purchase that keeps
   the buffer intact for 90 days; and a scenario planner
   (`POST /api/analytics/scenario`) that re-projects under revenue/expense
   deltas.
5. **Honesty guards**: `expected_error_pct` reports the backtested 4-week-
   aggregate error of the winning model (the error of the monthly numbers the
   UI shows); under 12 weeks of history the response carries
   `confidence: "low"`, widened bands, and a plain-language caveat.

Pure Python by design — no NumPy/statsmodels — to keep the install footprint
minimal (see docs/DECISIONS.md).

## The insight engine

Each rule in `services/insights.py` is an independent function of the user's data that
may emit one insight with a severity (`critical` → `warning` → `opportunity` →
`positive`) and, where computable, an estimated dollar impact. Adding a rule is
appending one block — no framework. Every number in insight copy is computed from
the user's own data; there are no canned industry statistics. Current rules:
overdue collections, forecast cash-low alert (surfaces the forecasting engine's
`cash_low_alert` with its projected date and shortfall), runway pressure, chronic
late payers (per-customer average days past due from `paid_date` history),
revenue concentration, per-category expense spikes (single month), category
quarter-over-quarter growth trends (three complete months vs. the prior three),
thin-margin pricing, three-month decline, growth momentum, and top-customer upsell.

## Frontend

Plain React + fetch (no state-management framework needed at this size). `lib/api.js`
centralizes the JWT header, 401 → login redirect, and money/date formatting. Charts
are Recharts. The design system lives in `styles.css` as CSS custom properties.

**Error boundaries.** One wraps the whole app (catches a crash in `Login` or
`Shell` itself); one wraps the routed page content, keyed by pathname so a
crash on one page doesn't leave the fallback UI stuck after navigating away.
Neither replaces a page's own inline error handling for failed API calls —
they exist for the case an inline `try`/`catch` can't cover: a bug in a
render path.

**Code-splitting.** `Dashboard` and `Forecast` — the two pages that import
Recharts, the single largest dependency in the bundle — are lazy-loaded via
`React.lazy`/`Suspense` in `App.jsx`. Every other page (auth, ledger, CRUD)
loads without pulling in the chart library at all.

**Tests** (Vitest + React Testing Library, `npm test` in `frontend/`): the
api client (`lib/api.js` — formatting, token-expiry, request/error handling)
and the Forecast page's rendering states (loading, error, normal,
low-confidence caveat, cash-low alert).
