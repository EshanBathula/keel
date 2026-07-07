"""Rolling-origin backtest math (hand-computed) and model selection on
synthetic series where the correct winner is knowable in advance."""
import math

from app.services.forecast.backtest import (
    aggregate_error_pct, select_best_model, signed_residuals,
)


def _constant_model(train, horizon):
    """Test double: always predicts 100, regardless of history."""
    return [100.0] * horizon


def test_signed_residuals_hand_computed():
    # Series [100, 110, 120, 130, 140], holdout=2 -> evaluate points at
    # indices 3 and 4 against a model that always predicts 100:
    #   residual@3 = 130 - 100 = 30
    #   residual@4 = 140 - 100 = 40
    series = [100.0, 110.0, 120.0, 130.0, 140.0]
    assert signed_residuals(_constant_model, series, holdout=2) == [30.0, 40.0]


def test_signed_residuals_expanding_window_never_sees_future():
    # A model that predicts its training set's last value ("naive"). With
    # series [1..6] and holdout=3, predictions must be train[-1] of the
    # expanding prefix, NOT the actual value being scored:
    #   i=3: train=[1,2,3] -> predict 3, actual 4 -> residual 1
    #   i=4: train=[1..4]  -> predict 4, actual 5 -> residual 1
    #   i=5: train=[1..5]  -> predict 5, actual 6 -> residual 1
    naive = lambda train, horizon: [train[-1]] * horizon
    series = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert signed_residuals(naive, series, holdout=3) == [1.0, 1.0, 1.0]


def test_signed_residuals_insufficient_history_returns_empty():
    assert signed_residuals(_constant_model, [1.0, 2.0], holdout=8) == []


def test_aggregate_error_pct_hand_computed():
    # Series 100..190 (n=10), constant-100 model, agg_weeks=2, holdout=3:
    #   first origin = 10-3-2+1 = 6; origins 6, 7, 8
    #   origin 6: pred = 200, actual = 160+170 = 330 -> err 130
    #   origin 7: pred = 200, actual = 170+180 = 350 -> err 150
    #   origin 8: pred = 200, actual = 180+190 = 370 -> err 170
    #   MAE = 150; mean actual = 350 -> 150/350 = 42.857 -> 42.9
    series = [100.0 + 10 * i for i in range(10)]
    assert aggregate_error_pct(_constant_model, series, agg_weeks=2, holdout=3) == 42.9


def test_aggregate_error_pct_insufficient_history_returns_none():
    # n=5 with holdout=8, agg=4 -> first origin would be negative.
    assert aggregate_error_pct(_constant_model, [1.0] * 5) is None


def test_aggregate_error_pct_zero_actuals_returns_none():
    assert aggregate_error_pct(_constant_model, [0.0] * 20) is None


def test_select_best_model_insufficient_history_falls_back():
    name, residuals = select_best_model([100.0] * 5, holdout=8)
    assert name == "ols_ma_blend"
    assert residuals == []


def test_selection_seasonal_series_picks_seasonal_naive():
    # Strong 52-week seasonality, no trend, deterministic small noise.
    # Seasonal-naive nails each held-out week using last year's same week;
    # trend models can't represent the oscillation and must lose.
    noise = [((i * 37) % 13) - 6 for i in range(200)]
    series = [
        1000 + 400 * math.sin(2 * math.pi * (i % 52) / 52) + noise[i]
        for i in range(70)
    ]
    name, residuals = select_best_model(series)
    assert name == "seasonal_naive"
    assert len(residuals) == 8


def test_selection_decelerating_growth_picks_damped_trend():
    # Growth that tapers toward a plateau — exactly the shape damping exists
    # for. Seasonal-naive (52-week lookback unavailable -> falls back to
    # last-value) and the OLS blend (dragged down by its long moving-average
    # window) both underfit the recent flattening curve.
    series, level, increment = [], 1000.0, 400.0
    for _ in range(30):
        series.append(level)
        level += increment
        increment *= 0.85
    name, _ = select_best_model(series)
    assert name == "damped_trend"


def test_selection_mae_is_the_criterion():
    # Force a tie-breaking situation we can reason about: on a linear series,
    # a 1-step-ahead damped/OLS forecast tracks closely while seasonal-naive
    # (last-value fallback) lags by one slope-step every week. Whatever wins
    # must have the smallest MAE — recompute MAEs independently and check.
    from app.services.forecast.backtest import HOLDOUT_WEEKS
    from app.services.forecast.models import CANDIDATES

    series = [100.0 + 7.0 * i for i in range(30)]
    name, residuals = select_best_model(series)

    maes = {}
    for candidate, fn in CANDIDATES.items():
        r = signed_residuals(fn, series, HOLDOUT_WEEKS)
        maes[candidate] = sum(abs(x) for x in r) / len(r)
    assert name == min(maes, key=maes.get)
    got_mae = sum(abs(x) for x in residuals) / len(residuals)
    assert math.isclose(got_mae, maes[name])
