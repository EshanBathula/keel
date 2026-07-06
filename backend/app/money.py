"""Cent-precise money conversions.

Ledger arithmetic (models, services) operates on integer cents so that summing
many transactions never accumulates binary floating-point drift. Dollars —
plain floats — exist only at the API boundary (request/response bodies) for
human ergonomics; see docs/DECISIONS.md.
"""
from decimal import Decimal, ROUND_HALF_UP


def to_cents(dollars) -> int:
    """Convert a dollar amount (float, int, str, or Decimal) to integer cents.

    Rounds half-up to the nearest cent so float input noise (e.g.
    19.999999999998 from JSON) collapses to the intended value.
    """
    return int((Decimal(str(dollars)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_dollars(cents: int) -> float:
    """Convert integer cents to a dollar float for API responses."""
    return float(Decimal(cents) / 100)
