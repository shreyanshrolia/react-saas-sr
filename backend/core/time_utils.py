"""Datetime/string helpers used across services."""
from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def parse_iso(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return now_utc()


def month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def current_month_key() -> str:
    return month_key(now_utc())
