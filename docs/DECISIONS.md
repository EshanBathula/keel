# Decisions

Judgment calls made during the v2 upgrade, and known issues found along the way.
Newest first within each task.

## Task 4 — Ledger completeness

**`GET /api/transactions` response shape changed: bare array → `{items, total,
limit, offset}`.** This is a breaking change to an existing endpoint, made
deliberately rather than adding a second paginated endpoint alongside it —
carrying two list endpoints forward would be the kind of complexity that
doesn't earn its place. Default page size dropped from 200 to 25 now that
pagination is real (previously "pagination" was really just a large,
un-paginated cap). Frontend `Transactions.jsx` and the existing tests that
asserted a bare array were updated to match.

**Transaction edit is `PATCH`, not `PUT`, mirroring the existing invoice
pattern.** Partial updates use `payload.model_dump(exclude_unset=True))` so a
field genuinely absent from the request body is left untouched — including
the amount property setter, which converts dollars → cents transparently
the same way `create_transaction` already does, so `PATCH` needed no new
money-conversion code.

**Text search is substring, across category + description, case-insensitive
(`ilike`).** Simplest thing that answers "find me that expense" without
building a query-string mini-language. Exact `category=` match is left
in place alongside it for backward compatibility, though the UI only exposes
the free-text search.

**Fixed a cross-tenant data leak found while touching create/update:**
`create_transaction`, `update_transaction`, and `create_invoice` accepted a
`customer_id` with no check that it belonged to the caller. Since queries
that resolve `tx.customer.name` don't re-filter by `user_id` (they trust the
FK), a transaction could be linked to another tenant's customer row and leak
that customer's name into `top_customers`/analytics for the wrong owner —
a violation of "every query filters by user_id" for data reached via a
relationship instead of a direct query. Fixed with a 3-line shared check
(`routers/_util.py::ensure_customer_owned`) used by all three write paths;
covered by `test_transaction_update_rejects_other_users_customer` and
`test_invoice_rejects_other_users_customer`. This wasn't explicitly listed
in the task but falls under "fix bugs you find rather than silently ignore."

**Timezone: nullable `users.timezone`, validated as a real IANA zone at
write time, resolved once per request via `app/tz.py::user_today()`.**
Every router call that used to pass an implicit `today=date.today()` default
now explicitly passes `user_today(user)` — `analytics.py` (kpis, monthly,
categories, forecast, insights) and `invoices.py` (overdue auto-flagging,
the invoice-paid transaction's date). Doing the invoice-side boundary too
wasn't explicitly asked for ("use it for 'this month' boundaries"), but
leaving invoices on server-UTC while KPIs use the user's timezone would mean
an invoice could flip to `overdue` on a different calendar day than the
dashboard thinks "today" is — an inconsistency a skeptical reviewer would
catch immediately. `user_today()` takes an optional `now` for testability
(same pattern as the rate limiter's `allow(key, now=...)`) — the three
hand-computed unit tests in `test_tz.py` pick one UTC instant that resolves
to three different calendar dates depending on zone (UTC-12, UTC, UTC+14),
so the boundary-crossing behavior is provably correct without depending on
wall-clock time when tests run.

**No dedicated settings API — reused `PATCH /api/auth/me`.** Business name
and timezone are both user-profile fields; a separate `/api/settings`
endpoint would just be `/api/auth/me` with extra ceremony. Added a minimal
frontend Settings page (business name + timezone, with a one-click "use your
browser's timezone" suggestion) since Task 4 needs *some* surface to set a
timezone after registration — registration itself doesn't ask for one to
keep the signup form unchanged.

### Known issues found (not yet fixed)

- Frontend inline-edit and filter changes have no debounce; every keystroke
  in the transaction search box fires a request. Acceptable at demo/small-
  business data volumes; would want debouncing before this sees a ledger with
  thousands of rows and real network latency.

## Task 3 — Auth hardening

**Rate limiting: hand-rolled in-memory sliding window, not slowapi.** The task
allowed either. A dependency wasn't worth it for ~30 lines of logic
(`app/rate_limit.py`), and it keeps faith with the existing architecture note
that auth has zero heavyweight dependencies. Limits: 5 login attempts/minute/IP
(brute-force guard) and 5 registrations/hour/IP (signup-spam guard), keyed on
`request.client.host`. Known limitation: this is per-process, in-memory state —
it resets on restart and isn't shared across multiple backend workers/replicas.
Fine for the current single-process deployment; a multi-instance deployment
would need a shared store (Redis) instead. Tests reset both limiters in the
`fresh_db` autouse fixture, the same way the DB itself is reset per test —
otherwise ~25 tests sharing one `TestClient` (and therefore one source IP)
would trip each other's rate limits.

**`JWT_SECRET` production guard lives in `config.py`, checked at import time.**
Added an `ENV` setting (default `development`). When `ENV=production` and
`JWT_SECRET` is still the shipped default, `app.config` raises `RuntimeError`
immediately on import — before the app can serve a single request with a
publicly-known secret. The check is factored into `_check_production_secret()`
so it's unit-testable directly against a `Settings` instance, without needing
to reimport the whole app under different env vars.

**Frontend token-expiry: decode `exp` client-side to prevent a flash, but the
server stays the real authority.** Two changes to `lib/api.js` /
`App.jsx`: (1) `auth.isValid()` decodes the JWT's `exp` claim (no library,
no signature check — just informs the UI) so the `Protected` route can
redirect to `/login` *before* ever mounting a page or firing a doomed API call
against an already-expired token. (2) On a live 401 mid-session, `api()` now
returns a promise that never settles instead of throwing, because a
`window.location.href` redirect is already underway; letting the calling
page's `.catch()` run first would flash "Session expired" in the UI for a
frame before navigation actually happens. If JWT decoding fails for any reason
(malformed token), `isValid()` treats it as valid rather than expired — the
server-side 401 path still catches genuinely bad tokens, so failing open here
only risks one extra round trip, not a security gap.

**localStorage tokens, XSS tradeoff (kept as-is, not fixed this task).**
Tokens still live in `localStorage`, readable by any JS running on the page.
The task explicitly asked to document this rather than fix it now. Risk: if
the frontend ever ships a script-injection bug, the attacker's script can read
the token directly (no `dangerouslySetInnerHTML` exists in the codebase today
— grepped to confirm — so there's no known vector, but the tradeoff exists
independent of current code). The safer alternative is an httpOnly,
`SameSite=Strict` cookie, which JS can't read at all — but that requires CSRF
protection (cookies ride along on any cross-site request automatically,
tokens in headers don't) and changes the auth flow enough that it's a
separate, deliberate migration rather than a drive-by fix alongside rate
limiting and the JWT-secret check.

### Known issues found (not yet fixed)

- Rate limiting is IP-keyed only; a login limiter shared across users behind
  one NAT/proxy could let one noisy client lock out others on the same IP.
  Acceptable for a self-hosted small-business app (task explicitly asked for
  "simple"), but worth revisiting if Keel is ever deployed multi-tenant behind
  a shared egress IP (e.g. corporate VPN).

## Task 2 — Alembic migrations

**Two migrations, not one.** `alembic/versions/d3fc1e4ef268_baseline_schema.py`
hand-recreates the schema exactly as it shipped in v1.0 (commit `8f69432`,
`Float` amount columns) — this is the migration path anyone with a real v1.0
database needs to start from. `18851eed2a8a_money_as_integer_cents.py` then
applies Task 1's change as an actual reversible migration: add
`amount_cents`, backfill it from `amount` using `app.money.to_cents` (the
exact function the app uses, so the migration and the app can never disagree
on rounding), then drop `amount`. `downgrade()` reverses it with
`to_dollars`. A fresh clone runs both in sequence and ends up at the same
schema `models.py` describes today — verified by running
`alembic revision --autogenerate` against a freshly-migrated database and
confirming it detects zero diff (empty migration generated, then discarded).

**`render_as_batch=True`** is set in `alembic/env.py` for both online and
offline migration contexts. SQLite can't `ALTER COLUMN` or `DROP COLUMN`
directly — Alembic's batch mode works around this by rebuilding the table.
Harmless for Postgres too, so it's left on unconditionally rather than
branching on dialect.

**`create_all()` removed from `main.py` and `seed.py`.** Only
`backend/tests/test_api.py` still calls
`Base.metadata.create_all()`/`drop_all()` directly, per the task's explicit
carve-out — tests want a fast, fully-isolated schema per run, not a
migration chain. Production/dev now rely on `alembic upgrade head`, which the
Docker image runs automatically before starting uvicorn (see `Dockerfile`
`CMD`).

## Task 1 — Money as integer cents

**Storage & arithmetic: integer cents. Wire format: dollars.** `Transaction` and
`Invoice` now store `amount_cents` (`Integer`) instead of `amount` (`Float`).
The public API request/response bodies are unchanged — `amount` is still a
plain dollar number in JSON, matching the existing examples in `docs/API.md`
— because the actual bug being fixed is silent float drift from *summing many
transactions*, not the shape of a single value at the edge. Rounding a lone
dollar amount to a float for display loses nothing; summing thousands of them
as floats does.

Two approaches were considered for the API boundary:
1. Expose `amount_cents` (int) end-to-end, including JSON. Most rigorous, but
   breaks the existing API contract and forces every frontend page that reads
   or writes an amount to add `/100` or `*100`.
2. Keep dollars at the API edge, cents everywhere else. Chosen — it isolates
   the fix to the layer that actually had the bug (ledger aggregation) and
   keeps the blast radius to models/services instead of every router, schema,
   and page.

**How the conversion is invisible to routers/seed/schemas:** `Transaction` and
`Invoice` gained an `amount` `@property` (getter divides `amount_cents` by
100 via `Decimal`; setter multiplies and rounds half-up back to cents). Since
SQLAlchemy's generated `__init__` does a plain `setattr` per kwarg,
`Transaction(amount=19.99, ...)` still works everywhere it already did
(routers, CSV import, `seed.py`) — those call sites needed zero changes.
`backend/app/money.py` holds the two conversion functions
(`to_cents`/`to_dollars`), both `Decimal`-based so `Decimal(str(dollars))`
round-trips through Python's shortest-repr float formatting instead of
capturing binary float noise.

**All arithmetic in cents, not just storage.** `services/analytics.py` gained
`monthly_series_cents()` — the actual summation of every transaction in a
month happens over `int` cents. `monthly_series()` (dollars, used by the
`/api/analytics/monthly` route) and `compute_kpis()` both build on top of it,
converting to dollars only once, at the return statement. `services/forecast.py`
was changed the same way: OLS/moving-average projection runs on cents, and
`to_dollars()` is applied only to the final `ForecastPoint` fields. This
matters because a business with hundreds of transactions per month would
otherwise reintroduce exactly the float-summation bug this task exists to fix,
just at the aggregation layer instead of the storage layer.

**Invoice-paid transaction copies `amount_cents` directly.** The
"paid invoice creates an income transaction" code in
`routers/invoices.py:update_invoice` used to do
`Transaction(..., amount=inv.amount, ...)`, round-tripping cents → dollars →
cents. That round trip is provably lossless given `to_cents`/`to_dollars`'s
`Decimal` + shortest-repr design (see `test_round_trip_stable_across_range`),
but there's no reason to rely on that when the source value is already exact:
the new code sets `tx.amount_cents = inv.amount_cents` directly.

**Rounding mode: half-up, silent.** Amounts that don't fall exactly on a cent
(typically float noise from JSON, e.g. `19.999999999998`) are rounded to the
nearest cent rather than rejected. This matches how e.g. Stripe's API
behaves and avoids rejecting legitimate values a browser's `<input
type=number>` might produce.

**XSS / localStorage tradeoff:** tracked under Task 3, not here.

### Known issues found (not yet fixed)

- `analytics.py::compute_kpis` sums 12 already-rounded monthly dollar
  values (`cash = sum(...)`) to compute cash runway. This is technically a
  float sum, but over only 12 terms that are themselves derived from exact
  cents — the residual error is many orders of magnitude below a cent and
  invisible after rounding for display. Left as-is; flagging so it isn't
  mistaken for an oversight.
- `avg_monthly_burn` is computed as `round(sum(cents)/len(cents))`, i.e.
  rounded to a whole cent — a bankers'-rounding-free integer division of an
  average is inherently a smoothing step, not a ledger balance, so this is
  intentional and not a precision bug.
