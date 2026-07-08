"""Unit tests for the three candidate models and the percentile helper.
Expected values are hand-computed.
"""

from app.services.forecast.models import (
    damped_trend,
    ols_ma_blend,
    percentile,
    seasonal_naive,
)


def test_seasonal_naive_uses_last_cycle_when_history_long_enough():
    # 53 weeks: index 0 is "52 weeks before" index 52. Predicting 1 week past
    # the end (index 53) should reuse index 53-52=1's value, i.e. train[1].
    train = list(range(100, 100 + 53))  # [100, 101, ..., 152]
    out = seasonal_naive(train, horizon=3)
    # h=1 -> idx = 53+1-1-52 = 1 -> train[1] = 101
    # h=2 -> idx = 2 -> train[2] = 102
    # h=3 -> idx = 3 -> train[3] = 103
    assert out == [101, 102, 103]


def test_seasonal_naive_falls_back_to_last_value_when_history_short():
    train = [10.0, 20.0, 30.0]  # far fewer than 52 weeks
    out = seasonal_naive(train, horizon=4)
    assert out == [30.0, 30.0, 30.0, 30.0]


def test_seasonal_naive_empty_history():
    assert seasonal_naive([], horizon=2) == [0.0, 0.0]


def test_ols_ma_blend_flat_series_predicts_flat():
    train = [500.0] * 10
    out = ols_ma_blend(train, horizon=3)
    # Zero slope, MA == 500 -> blended == 500 for every step.
    assert out == [500.0, 500.0, 500.0]


def test_ols_ma_blend_empty_history():
    assert ols_ma_blend([], horizon=2) == [0.0, 0.0]


def test_damped_trend_flat_series_predicts_flat():
    train = [200.0] * 6
    out = damped_trend(train, horizon=3)
    # No trend anywhere in a flat series -> every fitted trend is 0,
    # so the forecast should just hold the level.
    assert out == [200.0, 200.0, 200.0]


def test_damped_trend_single_point_holds_last_value():
    assert damped_trend([42.0], horizon=2) == [42.0, 42.0]


def test_damped_trend_empty_history():
    assert damped_trend([], horizon=2) == [0.0, 0.0]


def test_percentile_hand_computed():
    # Sorted values 10..100 step 10 (10 values, indices 0..9).
    values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    # p=50 -> k = 0.5*9 = 4.5 -> interpolate between values[4]=50 and values[5]=60 -> 55
    assert percentile(values, 50) == 55.0
    # p=0 -> k=0 -> values[0] = 10
    assert percentile(values, 0) == 10.0
    # p=100 -> k=9 -> values[9] = 100
    assert percentile(values, 100) == 100.0
    # p=10 -> k = 0.1*9 = 0.9 -> interpolate values[0]=10, values[1]=20 -> 10*0.1+20*0.9 = 19
    assert percentile(values, 10) == 19.0


def test_percentile_single_value():
    assert percentile([7.0], 10) == 7.0
    assert percentile([7.0], 90) == 7.0


def test_percentile_empty():
    assert percentile([], 50) == 0.0
