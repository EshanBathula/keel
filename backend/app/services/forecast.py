"""Cash-flow forecasting.

Uses ordinary least-squares trend on the trailing months, blended with a
3-month moving average to damp noise, plus a residual-based confidence band.
Pure Python by design: no heavyweight numeric dependencies.
"""
from datetime import date

from sqlalchemy.orm import Session

from .analytics import monthly_series, shift_month


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


def _project(values: list[float], horizon: int) -> list[tuple[float, float]]:
    """Project `horizon` future values; returns [(point, band_halfwidth)]."""
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
        out.append((round(blended, 2), round(band, 2)))
    return out


def forecast(db: Session, user_id: int, horizon: int = 6, today: date | None = None) -> list[dict]:
    today = today or date.today()
    series = monthly_series(db, user_id, months=12, today=today)
    # Drop leading empty months so a young business isn't dragged toward zero.
    while len(series) > 3 and series[0]["revenue"] == 0 and series[0]["expenses"] == 0:
        series.pop(0)

    revenues = [p["revenue"] for p in series]
    expenses = [p["expenses"] for p in series]
    rev_proj = _project(revenues, horizon)
    exp_proj = _project(expenses, horizon)

    last_month = series[-1]["month"]
    points = []
    for h in range(horizon):
        m = shift_month(last_month, h + 1)
        r, r_band = rev_proj[h]
        e, _ = exp_proj[h]
        net = round(r - e, 2)
        points.append({
            "month": m,
            "projected_revenue": r,
            "projected_expenses": e,
            "projected_net": net,
            "lower": round(max(r - r_band, 0.0), 2),
            "upper": round(r + r_band, 2),
        })
    return points
