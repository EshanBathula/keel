"""Cash-flow forecasting.

Uses ordinary least-squares trend on the trailing months, blended with a
3-month moving average to damp noise, plus a residual-based confidence band.
Pure Python by design: no heavyweight numeric dependencies.
"""
from datetime import date

from sqlalchemy.orm import Session

from .analytics import monthly_series_cents, shift_month
from ..money import to_dollars


def _ols(values: list[float]) -> tuple[float, float]:
    """Return (slope, intercept) of y = a*x + b over x = 0..n-1."""
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return 0.0, values[0]
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values)) / denom if denom else 0.0
    return slope, mean_y - slope * mean_x


def _residual_std(values: list[float], slope: float, intercept: float) -> float:
    n = len(values)
    if n < 3:
        return 0.0
    resid = [(y - (slope * x + intercept)) ** 2 for x, y in enumerate(values)]
    return (sum(resid) / (n - 2)) ** 0.5


def _project(values: list[int], horizon: int) -> list[tuple[int, int]]:
    """Project `horizon` future values (in cents); returns [(point_cents, band_halfwidth_cents)]."""
    slope, intercept = _ols(values)
    std = _residual_std(values, slope, intercept)
    ma = sum(values[-3:]) / len(values[-3:]) if values else 0.0
    n = len(values)
    out = []
    for h in range(1, horizon + 1):
        trend = slope * (n - 1 + h) + intercept
        blended = 0.6 * trend + 0.4 * ma          # damp aggressive trends
        blended = max(blended, 0.0)               # revenue/expenses can't go negative
        band = 1.28 * std * (1 + h * 0.15)        # ~80% band, widening with horizon
        out.append((round(blended), round(band)))
    return out


def forecast(db: Session, user_id: int, horizon: int = 6, today: date | None = None) -> list[dict]:
    today = today or date.today()
    series = monthly_series_cents(db, user_id, months=12, today=today)
    # Drop leading empty months so a young business isn't dragged toward zero.
    while len(series) > 3 and series[0]["revenue_cents"] == 0 and series[0]["expenses_cents"] == 0:
        series.pop(0)

    revenues = [p["revenue_cents"] for p in series]
    expenses = [p["expenses_cents"] for p in series]
    rev_proj = _project(revenues, horizon)
    exp_proj = _project(expenses, horizon)

    last_month = series[-1]["month"]
    points = []
    for h in range(horizon):
        m = shift_month(last_month, h + 1)
        r_cents, r_band_cents = rev_proj[h]
        e_cents, _ = exp_proj[h]
        net_cents = r_cents - e_cents
        points.append({
            "month": m,
            "projected_revenue": to_dollars(r_cents),
            "projected_expenses": to_dollars(e_cents),
            "projected_net": to_dollars(net_cents),
            "lower": to_dollars(max(r_cents - r_band_cents, 0)),
            "upper": to_dollars(r_cents + r_band_cents),
        })
    return points
