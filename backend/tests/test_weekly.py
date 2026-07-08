"""Unit tests for weekly bucketing helpers. Expected values are hand-computed."""

from datetime import date

from app.services.weekly import add_months, week_start


def test_week_start_is_monday():
    # 2026-07-07 is a Tuesday; its week starts Monday 2026-07-06.
    assert week_start(date(2026, 7, 7)) == date(2026, 7, 6)
    # A Monday maps to itself.
    assert week_start(date(2026, 7, 6)) == date(2026, 7, 6)
    # A Sunday belongs to the week that began 6 days earlier.
    assert week_start(date(2026, 7, 12)) == date(2026, 7, 6)


def test_add_months_clamps_to_month_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)  # leap year


def test_add_months_year_rollover():
    assert add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)
    assert add_months(date(2026, 7, 6), 6) == date(2027, 1, 6)
    assert add_months(date(2026, 7, 6), 0) == date(2026, 7, 6)
