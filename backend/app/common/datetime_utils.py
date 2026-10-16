"""Public wall times are Beijing; ordinary persisted instants are UTC.

Datetime objects come from trusted Python/ORM paths. Public strings must use
the exact wall-time format; never infer a timezone from the host environment.
"""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.common.constant import DATETIME_DISPLAY_FMT

BEIJING = ZoneInfo("Asia/Shanghai")
DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"


def as_utc(value: datetime) -> datetime:
    """Naive ordinary database timestamps have the project's UTC semantics."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def parse_beijing(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(DATETIME_PATTERN, value):
        raise ValueError("时间格式必须为 YYYY-MM-DD HH:mm:ss（北京时间）")
    try:
        return datetime.strptime(value, DATETIME_DISPLAY_FMT).replace(tzinfo=BEIJING)
    except ValueError as exc:
        raise ValueError("无效的日期时间") from exc


def datetime_input(value: str | datetime) -> datetime:
    return as_utc(value) if isinstance(value, datetime) else parse_beijing(value).astimezone(UTC)


def format_datetime(value: datetime) -> str:
    return as_utc(value).astimezone(BEIJING).strftime(DATETIME_DISPLAY_FMT)


def format_beijing_wall(value: datetime) -> str:
    """Explicit adapter for historical HTTP timestamps stored as Beijing wall time."""
    return (value.replace(tzinfo=BEIJING) if value.tzinfo is None else value.astimezone(BEIJING)).strftime(DATETIME_DISPLAY_FMT)


def beijing_stored_input(value: str | datetime) -> datetime:
    """Legacy last_login/session timestamps are Beijing, unlike base audit fields."""
    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=BEIJING)
    return datetime_input(value)
