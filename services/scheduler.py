"""Date assignment service for converting module JSON into dated study sessions."""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


load_dotenv()


def _next_weekday(d: date) -> date:
    """If date is Sat/Sun, move forward to Monday."""
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def build_schedule(
    modules: list[dict[str, Any]],
    *,
    start_date: date | None = None,
    timezone: str | None = None,
    session_start_hour: int | None = None,
    session_duration_minutes: int | None = None,
) -> list[dict[str, Any]]:
    """
    Hand-off in: [{sequence_no, title, content}, ...]
    Hand-off out: [{sequence_no, title, content, scheduled_date, start_datetime, end_datetime, timezone}, ...]
    """
    if not modules:
        return []

    tz_name = timezone or os.getenv("DEFAULT_TIMEZONE", "Asia/Kolkata")
    tz = ZoneInfo(tz_name)
    start_hour = session_start_hour or int(os.getenv("DEFAULT_SESSION_START_HOUR", "19"))
    duration = session_duration_minutes or int(os.getenv("DEFAULT_SESSION_DURATION_MINUTES", "90"))

    cursor = _next_weekday(start_date or datetime.now(tz).date())
    rows: list[dict[str, Any]] = []

    for module in sorted(modules, key=lambda x: int(x.get("sequence_no", 0))):
        cursor = _next_weekday(cursor)

        start_dt = datetime.combine(cursor, time(hour=start_hour, minute=0), tzinfo=tz)
        end_dt = start_dt + timedelta(minutes=duration)

        rows.append(
            {
                "sequence_no": int(module["sequence_no"]),
                "title": str(module["title"]),
                "content": str(module["content"]),
                "scheduled_date": cursor,
                "start_datetime": start_dt,
                "end_datetime": end_dt,
                "timezone": tz_name,
            }
        )

        cursor += timedelta(days=1)

    return rows