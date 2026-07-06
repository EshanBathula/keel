"""Unit tests for cent-precise money conversion. Expected values are hand-computed."""
from app.money import to_cents, to_dollars


def test_to_cents_basic():
    assert to_cents(19.99) == 1999
    assert to_cents("19.99") == 1999
    assert to_cents(1200.5) == 120050
    assert to_cents(0) == 0
    assert to_cents("0.01") == 1


def test_to_cents_rounds_half_up():
    # 0.005 dollars = 0.5 cents -> rounds up to 1 cent.
    assert to_cents(0.005) == 1
    # 19.995 dollars = 1999.5 cents -> rounds up to 2000 cents.
    assert to_cents(19.995) == 2000


def test_to_cents_absorbs_float_noise():
    # Binary floats can't represent 19.99 exactly; str(19.99) still round-trips
    # to "19.99" in Python, so this must land on 1999, not 1998 or 2000.
    assert to_cents(19.999999999998) == 2000


def test_to_dollars_basic():
    assert to_dollars(1999) == 19.99
    assert to_dollars(100) == 1.0
    assert to_dollars(1) == 0.01
    assert to_dollars(0) == 0.0


def test_round_trip_stable_across_range():
    for cents in [0, 1, 50, 99, 100, 1999, 120050, 999999]:
        assert to_cents(to_dollars(cents)) == cents
