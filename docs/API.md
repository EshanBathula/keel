# API Reference

Base URL: `http://localhost:8000`. All endpoints except `/api/auth/*` and
`/api/health` require `Authorization: Bearer <token>`. Interactive docs: `/docs`.

## Auth

### POST /api/auth/register
```json
{ "email": "you@example.com", "password": "min-8-chars", "business_name": "My Business",
  "timezone": "America/Chicago" }
```
→ `201` `{ "access_token": "...", "token_type": "bearer", "user": { ... } }`
`409` if the email is taken. `timezone` is optional (any IANA zone name);
`429` if rate-limited (5 registrations/hour/IP).

### POST /api/auth/login
```json
{ "email": "you@example.com", "password": "..." }
```
→ `200` with the same token payload. `401` on bad credentials, `429` if
rate-limited (5 attempts/minute/IP).

### GET /api/auth/me → current user.

### PATCH /api/auth/me
```json
{ "business_name": "New Name", "timezone": "America/Chicago" }
```
Both fields optional; only fields present in the body are changed.
`422` if `timezone` isn't a recognized IANA zone. The user's timezone (if
set) is used for "this month"/"today" boundaries across analytics, forecast,
insights, and invoice overdue-flagging — otherwise those fall back to UTC.

## Transactions

### GET /api/transactions?type=&category=&q=&date_from=&date_to=&limit=&offset=
Newest first, server-side paginated. `type` is `income` or `expense`;
`category` is an exact match; `q` is a case-insensitive substring search
across category and description; `date_from`/`date_to` are inclusive
(`YYYY-MM-DD`). `limit` defaults to 25 (max 200).
→ `{ "items": [...], "total": n, "limit": 25, "offset": 0 }`

### POST /api/transactions
```json
{ "type": "income", "amount": 1200.50, "category": "Services",
  "description": "Consulting", "date": "2026-07-01", "customer_id": 3 }
```
`400` if `customer_id` doesn't belong to the caller.

### PATCH /api/transactions/{id}
Same fields as create, all optional — only fields present in the body are
changed. `404` if the transaction isn't the caller's, `400` if `customer_id`
doesn't belong to the caller.

### DELETE /api/transactions/{id} → `204`

### POST /api/transactions/import  (multipart)
CSV with header `date,type,amount,category,description`. Dates accept
`YYYY-MM-DD` or `MM/DD/YYYY`. Returns `{ "created": n, "errors": ["line 4: ..."] }` —
bad rows are skipped, good rows still import.

## Customers

`GET /api/customers` · `POST /api/customers` (`name`, `email`, `notes`) ·
`DELETE /api/customers/{id}`

## Invoices

### GET /api/invoices
Sent invoices past their due date are auto-flagged `overdue` on read.

### POST /api/invoices
```json
{ "customer_id": 3, "number": "INV-1007", "amount": 2500,
  "status": "sent", "issue_date": "2026-07-01", "due_date": "2026-07-31" }
```

### PATCH /api/invoices/{id}
```json
{ "status": "paid" }
```
Transitioning to `paid` automatically records an income transaction for the
amount and stamps `paid_date` (used to compute each customer's on-time
payment rate for the forecast and the late-payer insight).

## Analytics

### GET /api/analytics/kpis
```json
{
  "revenue_this_month": 17507.9, "revenue_last_month": 17188.81,
  "revenue_growth_pct": 1.9, "expenses_this_month": 11034.14,
  "net_this_month": 6473.76, "profit_margin_pct": 37.0,
  "avg_monthly_burn": 9691.35, "cash_runway_months": 8.9,
  "outstanding_receivables": 9755.08, "overdue_receivables": 6761.43,
  "health_score": 83, "health_grade": "B"
}
```

### GET /api/analytics/monthly?months=12
`[{ "month": "2026-07", "revenue": 17507.9, "expenses": 11034.14, "net": 6473.76 }, ...]`

### GET /api/analytics/categories?type=expense&months=12
Totals per category, descending.

### GET /api/analytics/top-customers?limit=5
Revenue and share of total per customer.

### GET /api/analytics/forecast?horizon=6
`horizon` is in months (1–12). Weekly-granularity, cash-aware projection:

```json
{
  "confidence": "normal",
  "model_revenue": "damped_trend",
  "model_expenses": "ols_ma_blend",
  "expected_error_pct": 21.8,
  "weekly": [
    { "week_start": "2026-07-13", "cash_p10": 82413.08,
      "cash_p50": 87929.94, "cash_p90": 94930.04 }, ...
  ],
  "monthly": [
    { "month": "2026-08", "projected_revenue": 18935.13,
      "projected_expenses": 9987.0, "projected_net": 8948.13,
      "lower": 16910.86, "upper": 20959.4 }, ...
  ],
  "min_cash_balance": 87929.94,
  "min_cash_balance_date": "2026-07-13",
  "cash_low_alert": null,
  "safe_to_spend": 72721.73,
  "caveat": null
}
```

- Models compete per user via rolling-origin backtest (last 8 weeks, walk
  forward, MAE); `model_revenue`/`model_expenses` name each winner.
- `expected_error_pct` is that model's backtested error on 4-week aggregates —
  "typically within ±X%" for the monthly figures shown.
- `weekly` is the projected cash-balance curve with empirical P10/P50/P90
  bands; unpaid invoices contribute on their due dates, weighted by each
  customer's historical on-time payment rate.
- `cash_low_alert` is non-null (`{week_start, shortfall}`) when the P10 curve
  dips below a one-month expense buffer; `safe_to_spend` is the largest
  one-time purchase that keeps the buffer intact over the next 90 days.
- With under 12 weeks of history, `confidence` is `"low"`, bands widen, and
  `caveat` carries a plain-language warning.

### POST /api/analytics/scenario?horizon=6
```json
{ "monthly_revenue_change_pct": 10 }
```
or
```json
{ "new_monthly_expense_cents": 400000, "start_month": "2026-09" }
```
(or both). Returns the same shape as `/forecast`, re-projected under the
deltas. `422` if `start_month` isn't `YYYY-MM`.

### GET /api/analytics/insights
Prioritized list: `{ "id", "severity", "title", "detail", "estimated_impact" }`,
severity ∈ `critical | warning | opportunity | positive`.
