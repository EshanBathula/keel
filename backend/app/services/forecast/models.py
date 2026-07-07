"""Three candidate forecasting models, all with the same interface:

    predict(train: list[float], horizon: int) -> list[float]

`train` is a chronologically-ordered weekly series (in cents); returns a
point forecast for each of the next `horizon` weeks. Pure Python throughout —
no NumPy/pandas/statsmodels — see docs/DECISIONS.md for why.
"""
import math

SEASONAL_PERIOD_WEEKS = 52


def seasonal_naive(train: list[float], horizon: int) -> list[float]:
    """Forecast = the value from the same week one cycle (52 weeks) ago.

    Falls back to the last observed value when there isn't a full cycle of
    history yet — a defensible degrade-to-naive behavior for young accounts,
    rather than refusing to forecast at all.
    """
    n = len(train)
    last = train[-1] if train else 0.0
    out = []
    for h in range(1, horizon + 1):
        idx = n + h - 1 - SEASONAL_PERIOD_WEEKS
        out.append(train[idx] if 0 <= idx < n else last)
    return out


def _fit_damped_trend(train: list[float], alpha: float, beta: float, phi: float) -> tuple[float, float, float]:
    """One pass of Holt's damped-trend smoothing.

    Returns (level, trend, in_sample_sse) — the SSE of one-step-ahead fitted
    errors, used to grid-search (alpha, beta, phi) below.
    """
    n = len(train)
    level = train[0]
    trend = train[1] - train[0] if n > 1 else 0.0
    sse = 0.0
    for t in range(1, n):
        pred = level + phi * trend  # one-step-ahead prediction made at t-1
        err = train[t] - pred
        sse += err * err
        new_level = alpha * train[t] + (1 - alpha) * (level + phi * trend)
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        level = new_level
    return level, trend, sse


# Coarse grid, not full MLE optimization (see docs/DECISIONS.md) — cheap
# enough to brute-force for weekly series of realistic length.
_ALPHA_GRID = (0.2, 0.4, 0.6, 0.8)
_BETA_GRID = (0.1, 0.3, 0.5)
_PHI_GRID = (0.8, 0.9, 0.98)


def damped_trend(train: list[float], horizon: int) -> list[float]:
    """Holt's linear trend method with damping (Gardner & McKenzie).

    The damping parameter phi<1 makes the trend taper off over the horizon
    instead of extrapolating the last slope forever — better suited to
    decelerating growth than a plain linear (OLS) trend.
    """
    if not train:
        return [0.0] * horizon
    if len(train) < 2:
        return [train[-1]] * horizon

    best_sse = math.inf
    best = (train[-1], 0.0, _PHI_GRID[0])
    for alpha in _ALPHA_GRID:
        for beta in _BETA_GRID:
            for phi in _PHI_GRID:
                level, trend, sse = _fit_damped_trend(train, alpha, beta, phi)
                if sse < best_sse:
                    best_sse = sse
                    best = (level, trend, phi)
    level, trend, phi = best

    out = []
    phi_power_sum = 0.0
    for h in range(1, horizon + 1):
        phi_power_sum += phi ** h
        out.append(level + phi_power_sum * trend)
    return out


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


_MA_WINDOW_WEEKS = 8


def ols_ma_blend(train: list[float], horizon: int) -> list[float]:
    """OLS trend blended 60/40 with an 8-week moving average, damping
    overreaction to a short trailing trend — Keel v1's original approach,
    ported from monthly to weekly cadence."""
    if not train:
        return [0.0] * horizon
    slope, intercept = _ols(train)
    window = train[-_MA_WINDOW_WEEKS:]
    ma = sum(window) / len(window)
    n = len(train)
    out = []
    for h in range(1, horizon + 1):
        trend = slope * (n - 1 + h) + intercept
        out.append(0.6 * trend + 0.4 * ma)
    return out


CANDIDATES = {
    "seasonal_naive": seasonal_naive,
    "damped_trend": damped_trend,
    "ols_ma_blend": ols_ma_blend,
}


def percentile(sorted_values: list[float], p: float) -> float:
    """Linear-interpolated percentile (0-100) of a PRE-SORTED list.

    Matches numpy's default ('linear') method — used so backtest residual
    bands are empirical quantiles, not an assumed distribution.
    """
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (p / 100) * (len(sorted_values) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)
