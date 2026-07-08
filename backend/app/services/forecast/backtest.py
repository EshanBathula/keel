"""Rolling-origin (walk-forward) backtest and model selection.

For each held-out week, a model is trained on only the data available before
that week and asked for a genuine 1-step-ahead forecast — never fit with
hindsight on the value it's predicting. This is what makes it a fair proxy
for how the model will perform on next week's real, unseen data.
"""

from .models import CANDIDATES

HOLDOUT_WEEKS = 8


def signed_residuals(model_fn, series: list[float], holdout: int = HOLDOUT_WEEKS) -> list[float]:
    """(actual - predicted) for each of the last `holdout` points, predicted
    1-step-ahead from an expanding training window. Empty if there isn't
    enough history to hold out `holdout` points at all."""
    n = len(series)
    if n <= holdout:
        return []
    return [series[i] - model_fn(series[:i], horizon=1)[0] for i in range(n - holdout, n)]


AGG_WEEKS = 4


def aggregate_error_pct(
    model_fn, series: list[float], agg_weeks: int = AGG_WEEKS, holdout: int = HOLDOUT_WEEKS
) -> float | None:
    """Walk-forward relative error of `agg_weeks`-week SUMS — the error of what
    the user actually reads (monthly totals), not of individual weeks.

    For lumpy payers (all revenue landing in 1-2 weeks a month), weekly
    1-step errors run near 100% of the weekly average while the monthly
    total is still forecast well — quoting the weekly figure against monthly
    numbers would be misleadingly pessimistic. Selection still happens on
    weekly MAE (select_best_model); this only scales the reported error to
    the reported quantity. Returns None when history is too short.
    """
    n = len(series)
    first = n - holdout - agg_weeks + 1
    if first < 1:
        return None
    errs, actuals = [], []
    for i in range(first, n - agg_weeks + 1):
        pred = sum(model_fn(series[:i], horizon=agg_weeks))
        actual = sum(series[i : i + agg_weeks])
        errs.append(abs(pred - actual))
        actuals.append(actual)
    mean_actual = sum(actuals) / len(actuals)
    if mean_actual <= 0:
        return None
    return round(sum(errs) / len(errs) / mean_actual * 100, 1)


def select_best_model(series: list[float], holdout: int = HOLDOUT_WEEKS) -> tuple[str, list[float]]:
    """Return (winning_model_name, its_signed_residuals).

    Falls back to "ols_ma_blend" with no residuals when there isn't enough
    history to backtest at all (n <= holdout) — callers should treat an empty
    residuals list as "can't honestly quantify error" and widen/flag
    accordingly rather than pretending precision.
    """
    best_name, best_residuals, best_mae = None, [], float("inf")
    for name, fn in CANDIDATES.items():
        residuals = signed_residuals(fn, series, holdout)
        if not residuals:
            continue
        mae = sum(abs(r) for r in residuals) / len(residuals)
        if mae < best_mae:
            best_name, best_residuals, best_mae = name, residuals, mae
    if best_name is None:
        return "ols_ma_blend", []
    return best_name, best_residuals
