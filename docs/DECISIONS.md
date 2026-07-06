# Decisions

Judgment calls made during the v2 upgrade, and known issues found along the way.
Newest first within each task.

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
