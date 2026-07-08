"""User-local "today" resolution, for month/day boundaries that should follow
the business owner's clock rather than the server's.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import User


def user_today(user: User, now: datetime | None = None) -> date:
    """Resolve "today" in the user's IANA timezone.

    Falls back to UTC if the user hasn't set a timezone, or if the stored
    value isn't a recognized IANA zone (defensive — schema validation should
    prevent this, but data can predate that validation).
    """
    now = now or datetime.now(UTC)
    if user.timezone:
        try:
            return now.astimezone(ZoneInfo(user.timezone)).date()
        except ZoneInfoNotFoundError:
            pass
    return now.astimezone(UTC).date()
