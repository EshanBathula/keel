"""Cash-flow forecasting engine.

Pipeline: weekly organic-revenue/expense history -> per-series model
competition via rolling-origin backtest -> forward projection -> known
invoice-cash overlay -> empirical-quantile cash bands -> actionable outputs
(min balance, cash_low_alert, safe_to_spend) -> monthly rollup for the chart.

See docs/DECISIONS.md for the reasoning behind each design choice below.
"""

import math
from datetime import date, timedelta

from sqlalchemy.orm import Session

from ...money import to_dollars
from ..analytics import approx_cash_balance_cents, avg_monthly_burn_cents, month_key
from ..weekly import add_months, week_start, weekly_series_cents
from .backtest import aggregate_error_pct, select_best_model
from .cash import scheduled_invoice_cash_cents
from .models import CANDIDATES, percentile

LOW_CONFIDENCE_WEEKS = 12
LOW_CONFIDENCE_BAND_WIDEN = 1.5
FALLBACK_BAND_FRACTION = 0.3
SAFE_TO_SPEND_DAYS = 90
WEEKS_HISTORY = 130  # ~2.5 years max lookback fetched for modeling

LOW_CONFIDENCE_CAVEAT = (
    "Less than 12 weeks of transaction history — this forecast is a rough estimate "
    "and its ranges are intentionally wide. Accuracy will improve as more data accumulates."
)


def _trimmed_history(db: Session, user_id: int, today: date) -> list[dict]:
    """Weekly series of COMPLETE weeks only, trimmed of leading all-zero weeks.

    The current in-progress week is excluded: its partial totals read as a
    sudden collapse to the models (e.g. seasonal-naive's last-value fallback
    would project the half-empty week forever). Its actual transactions still
    count via the starting cash balance. Leading all-zero weeks are trimmed so
    a young account isn't dragged toward zero by empty pre-history.
    """
    series = weekly_series_cents(db, user_id, weeks=WEEKS_HISTORY, today=today)
    series = series[:-1]  # drop the current, incomplete week
    while len(series) > 1 and series[0]["revenue_cents"] == 0 and series[0]["expenses_cents"] == 0:
        series.pop(0)
    return series


def _weekly_horizon_count(today: date, horizon_months: int) -> int:
    end = add_months(today, horizon_months)
    days = (end - week_start(today)).days
    return max(1, math.ceil(days / 7))


def _project_series(history: list[float], model_name: str, horizon: int) -> list[float]:
    """Project a trimmed weekly cents series forward with the named model,
    clamped at zero (revenue/expenses can't go negative)."""
    return [max(0.0, v) for v in CANDIDATES[model_name](history, horizon)]


def _weekly_bands(
    point_series: list[float],
    residuals: list[float],
    confidence: str,
    cumulative: bool,
    base: float = 0.0,
) -> tuple[list[float], list[float], list[float]]:
    """Per-week P10/P50/P90 from empirical backtest-residual quantiles,
    widening as sqrt(h) to reflect growing uncertainty over the horizon (the
    standard result for the spread of a sum of h roughly-independent errors).

    If `cumulative`, `point_series` values are summed running from `base`
    (for a cash balance curve); otherwise each week is banded independently
    (for a per-week revenue estimate). With no backtest residuals at all (not
    enough history), falls back to a crude fixed-fraction band — always
    paired with confidence="low" by the caller.
    """
    widen = LOW_CONFIDENCE_BAND_WIDEN if confidence == "low" else 1.0
    devs = None
    if residuals:
        s = sorted(residuals)
        devs = (percentile(s, 10), percentile(s, 50), percentile(s, 90))

    p10, p50, p90 = [], [], []
    running = base
    for h, v in enumerate(point_series, start=1):
        running = running + v if cumulative else v
        center = running
        if devs is None:
            spread = abs(center) * FALLBACK_BAND_FRACTION
            p10.append(center - spread)
            p50.append(center)
            p90.append(center + spread)
        else:
            scale = math.sqrt(h) * widen
            p10.append(center + devs[0] * scale)
            p50.append(center + devs[1] * scale)
            p90.append(center + devs[2] * scale)
    return p10, p50, p90


def _monthly_rollup(
    week_starts: list[date],
    rev_point: list[float],
    rev_p10: list[float],
    rev_p90: list[float],
    exp_point: list[float],
) -> list[dict]:
    buckets: dict[str, dict] = {}
    order = []
    for i, w in enumerate(week_starts):
        mk = month_key(w)
        if mk not in buckets:
            buckets[mk] = {"rev": 0.0, "rev_lo": 0.0, "rev_hi": 0.0, "exp": 0.0}
            order.append(mk)
        b = buckets[mk]
        b["rev"] += rev_point[i]
        b["rev_lo"] += rev_p10[i]
        b["rev_hi"] += rev_p90[i]
        b["exp"] += exp_point[i]
    return [
        {
            "month": mk,
            "projected_revenue": to_dollars(round(buckets[mk]["rev"])),
            "projected_expenses": to_dollars(round(buckets[mk]["exp"])),
            "projected_net": to_dollars(round(buckets[mk]["rev"] - buckets[mk]["exp"])),
            "lower": to_dollars(round(buckets[mk]["rev_lo"])),
            "upper": to_dollars(round(buckets[mk]["rev_hi"])),
        }
        for mk in order
    ]


def _min_balance(p50_curve: list[float], week_starts: list[date]) -> tuple[float, date]:
    idx = min(range(len(p50_curve)), key=lambda i: p50_curve[i])
    return p50_curve[idx], week_starts[idx]


def _cash_low_alert(p10_curve: list[float], week_starts: list[date], buffer_cents: float) -> dict | None:
    for i, bal in enumerate(p10_curve):
        if bal < 0 or bal < buffer_cents:
            return {"week_start": week_starts[i], "shortfall": to_dollars(round(buffer_cents - bal))}
    return None


def _safe_to_spend(
    p10_curve: list[float],
    week_starts: list[date],
    today: date,
    buffer_cents: float,
) -> float:
    cutoff = today + timedelta(days=SAFE_TO_SPEND_DAYS)
    window = [bal for w, bal in zip(week_starts, p10_curve, strict=True) if w <= cutoff]
    if not window:
        return 0.0
    return to_dollars(round(max(0.0, min(window) - buffer_cents)))


def _baseline_projection(db: Session, user_id: int, today: date, horizon_months: int) -> dict:
    history = _trimmed_history(db, user_id, today)
    confidence = "normal" if len(history) >= LOW_CONFIDENCE_WEEKS else "low"

    organic_rev_hist = [p["organic_revenue_cents"] for p in history]
    exp_hist = [p["expenses_cents"] for p in history]
    rev_model, rev_residuals = select_best_model(organic_rev_hist)
    exp_model, exp_residuals = select_best_model(exp_hist)

    horizon_weeks = _weekly_horizon_count(today, horizon_months)
    week_starts = [week_start(today) + timedelta(weeks=h) for h in range(1, horizon_weeks + 1)]

    organic_rev_point = _project_series(organic_rev_hist, rev_model, horizon_weeks)
    exp_point = _project_series(exp_hist, exp_model, horizon_weeks)

    # User-facing error is measured at 4-week-aggregate scale — the grain the
    # UI reports — not at the weekly grain used for model selection.
    expected_error_pct = aggregate_error_pct(CANDIDATES[rev_model], organic_rev_hist)

    return {
        "confidence": confidence,
        "rev_model": rev_model,
        "exp_model": exp_model,
        "rev_residuals": rev_residuals,
        "exp_residuals": exp_residuals,
        "week_starts": week_starts,
        "organic_rev_point": organic_rev_point,
        "exp_point": exp_point,
        "expected_error_pct": expected_error_pct,
    }


def _assemble_response(
    db: Session,
    user_id: int,
    today: date,
    week_starts: list[date],
    organic_rev_point: list[float],
    exp_point: list[float],
    rev_model: str,
    exp_model: str,
    rev_residuals: list[float],
    exp_residuals: list[float],
    confidence: str,
    expected_error_pct: float | None,
) -> dict:
    horizon_weeks = len(week_starts)
    invoice_cash = scheduled_invoice_cash_cents(db, user_id, week_starts, today=today)
    total_rev_point = [organic_rev_point[i] + invoice_cash.get(week_starts[i], 0) for i in range(horizon_weeks)]
    net_point = [total_rev_point[i] - exp_point[i] for i in range(horizon_weeks)]
    net_residuals = (
        [r - e for r, e in zip(rev_residuals, exp_residuals, strict=True)] if rev_residuals and exp_residuals else []
    )

    starting_cash = approx_cash_balance_cents(db, user_id, today=today)
    p10_cash, p50_cash, p90_cash = _weekly_bands(
        net_point, net_residuals, confidence, cumulative=True, base=starting_cash
    )
    rev_p10, _, rev_p90 = _weekly_bands(total_rev_point, rev_residuals, confidence, cumulative=False)

    monthly = _monthly_rollup(week_starts, total_rev_point, rev_p10, rev_p90, exp_point)
    min_balance, min_balance_date = _min_balance(p50_cash, week_starts)
    burn_cents = avg_monthly_burn_cents(db, user_id, today=today)
    alert = _cash_low_alert(p10_cash, week_starts, burn_cents)
    safe_to_spend = _safe_to_spend(p10_cash, week_starts, today, burn_cents)

    weekly = [
        {
            "week_start": w,
            "cash_p10": to_dollars(round(p10_cash[i])),
            "cash_p50": to_dollars(round(p50_cash[i])),
            "cash_p90": to_dollars(round(p90_cash[i])),
        }
        for i, w in enumerate(week_starts)
    ]

    return {
        "confidence": confidence,
        "model_revenue": rev_model,
        "model_expenses": exp_model,
        "expected_error_pct": expected_error_pct,
        "weekly": weekly,
        "monthly": monthly,
        "min_cash_balance": to_dollars(round(min_balance)),
        "min_cash_balance_date": min_balance_date,
        "cash_low_alert": alert,
        "safe_to_spend": safe_to_spend,
        "caveat": LOW_CONFIDENCE_CAVEAT if confidence == "low" else None,
    }


def forecast(db: Session, user_id: int, horizon_months: int = 6, today: date | None = None) -> dict:
    today = today or date.today()
    b = _baseline_projection(db, user_id, today, horizon_months)
    return _assemble_response(
        db,
        user_id,
        today,
        b["week_starts"],
        b["organic_rev_point"],
        b["exp_point"],
        b["rev_model"],
        b["exp_model"],
        b["rev_residuals"],
        b["exp_residuals"],
        b["confidence"],
        b["expected_error_pct"],
    )


def scenario(
    db: Session,
    user_id: int,
    monthly_revenue_change_pct: float | None = None,
    new_monthly_expense_cents: int | None = None,
    start_month: str | None = None,
    horizon_months: int = 6,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    b = _baseline_projection(db, user_id, today, horizon_months)
    organic_rev_point = b["organic_rev_point"]
    exp_point = b["exp_point"]

    if monthly_revenue_change_pct is not None:
        factor = 1 + monthly_revenue_change_pct / 100
        organic_rev_point = [max(0.0, v * factor) for v in organic_rev_point]

    if new_monthly_expense_cents is not None and start_month is not None:
        weekly_add = new_monthly_expense_cents * 12 / 52
        exp_point = [
            max(0.0, v + weekly_add) if month_key(w) >= start_month else v
            for v, w in zip(exp_point, b["week_starts"], strict=True)
        ]

    return _assemble_response(
        db,
        user_id,
        today,
        b["week_starts"],
        organic_rev_point,
        exp_point,
        b["rev_model"],
        b["exp_model"],
        b["rev_residuals"],
        b["exp_residuals"],
        b["confidence"],
        b["expected_error_pct"],
    )
