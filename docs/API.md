# API Reference

Base URL: `http://localhost:8000`. All endpoints except `/api/auth/*` and
`/api/health` require `Authorization: Bearer <token>`. Interactive docs: `/docs`.

## Auth

### POST /api/auth/register
```json
{ "email": "you@example.com", "password": "min-8-chars", "business_name": "My Business" }
```
→ `201` `{ "access_token": "...", "token_type": "bearer", "user": { ... } }`
`409` if the email is taken.

### POST /api/auth/login
```json
{ "email": "you@example.com", "password": "..." }
```
→ `200` with the same token payload. `401` on bad credentials.

### GET /api/auth/me → current user.

## Transactions

### GET /api/transactions?type=&category=&limit=&offset=
Newest first. `type` is `income` or `expense`.

### POST /api/transactions
```json
{ "type": "income", "amount": 1200.50, "category": "Services",
  "description": "Consulting", "date": "2026-07-01", "customer_id": 3 }
```

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
Transitioning to `paid` automatically records an income transaction for the amount.

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
```json
[{ "month": "2026-08", "projected_revenue": 18935.13, "projected_expenses": 9987.0,
   "projected_net": 8948.13, "lower": 16910.86, "upper": 20959.4 }, ...]
```

### GET /api/analytics/insights
Prioritized list: `{ "id", "severity", "title", "detail", "estimated_impact" }`,
severity ∈ `critical | warning | opportunity | positive`.
