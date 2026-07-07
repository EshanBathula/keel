"""Unit tests for user-local "today" resolution. Expected values are hand-computed."""
from datetime import date, datetime, timezone

from app.models import User
from app.tz import user_today


# 2026-01-01 10:01 UTC is simultaneously three different calendar dates
# depending on timezone: 2025-12-31 (UTC-12), 2026-01-01 (UTC), 2026-01-02 (UTC+14).
_NOW = datetime(2026, 1, 1, 10, 1, tzinfo=timezone.utc)


def test_user_today_uses_timezone_not_server_clock():
    behind = User(timezone="Etc/GMT+12")       # UTC-12
    ahead = User(timezone="Pacific/Kiritimati")  # UTC+14
    assert user_today(behind, now=_NOW) == date(2025, 12, 31)
    assert user_today(ahead, now=_NOW) == date(2026, 1, 2)


def test_user_today_falls_back_to_utc_when_unset():
    no_tz = User(timezone=None)
    assert user_today(no_tz, now=_NOW) == date(2026, 1, 1)


def test_user_today_falls_back_to_utc_on_invalid_timezone():
    bad = User(timezone="Not/AZone")
    assert user_today(bad, now=_NOW) == date(2026, 1, 1)
