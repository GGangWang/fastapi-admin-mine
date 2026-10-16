"""Historical HTTP wall-time adapter; audit logs use the ordinary framework type."""

from app.common.datetime_utils import format_beijing_wall as http_timestamp

__all__ = ["http_timestamp"]
