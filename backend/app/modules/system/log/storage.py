"""Monthly audit log storage. Legacy ORM tables remain migration sources only."""

import calendar
from datetime import UTC, datetime, timedelta
from functools import cache
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Index, Integer, MetaData, String, Table, delete, func, select, union_all
from sqlalchemy.orm import registry

from app.common.log_month import available_months, prepare_month, validate_month
from app.common.log_month import months as log_months
from app.core.exceptions import CustomException

from .model import LoginLogModel, OperationLogModel

TZ = ZoneInfo("Asia/Shanghai")
metadata = MetaData()
mapper_registry = registry(metadata=metadata)
# Compatibility export for immutable historical Alembic revisions only.
months = Table("sys_audit_log_month", MetaData(), Column("kind", String(16), primary_key=True), Column("month", String(6), primary_key=True), Column("version", Integer, nullable=False))
SOURCES = {"login": LoginLogModel, "operation": OperationLogModel}


def checked_month(month: str) -> str:
    try:
        return validate_month(month)
    except (ValueError, TypeError) as exc:
        raise CustomException(msg="日志月份必须是有效的 YYYYMM") from exc


def utc_time(value: datetime) -> datetime:
    # SQLAlchemy/SQLite returns naive UTC timestamps for DateTime(timezone=True).
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def record_month(value: datetime) -> str:
    return utc_time(value).astimezone(TZ).strftime("%Y%m")


def month_bounds(month: str) -> tuple[datetime, datetime]:
    start = datetime.strptime(checked_month(month), "%Y%m").replace(tzinfo=TZ)
    end = start.replace(day=calendar.monthrange(start.year, start.month)[1]) + timedelta(days=1)
    return start.astimezone(UTC), end.astimezone(UTC)


@cache
def month_model(kind: str, month: str):
    checked_month(month)
    source = SOURCES[kind].__table__
    name = source.name + "_" + month
    table = source.to_metadata(metadata, name=name)
    # PostgreSQL primary keys own schema-wide indexes: cloned names must also be unique.
    for constraint in table.constraints:
        if constraint.name is not None:
            constraint.name = str(constraint.name).replace(source.name, name)
    # Cloned explicit index names still refer to the source table; rename them.
    for index in table.indexes:
        index.name = name + "_" + "_".join(column.name for column in index.columns)
    Index(name + "_time_id", table.c.created_time, table.c.id)
    model = type(name, (), {})
    mapper_registry.map_imperatively(model, table)
    return model


def prepare_locked(connection, kind: str, month: str):
    prepare_month(connection, kind, month, month_model(kind, month).__table__, version=2)


async def prepare(engine, kind: str, month: str):
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: prepare_locked(conn, kind, month))


async def initialize(engine):
    from .upgrade import upgrade_ids
    await upgrade_ids(engine)
    now = datetime.now(TZ)
    following = now.replace(day=calendar.monthrange(now.year, now.month)[1]) + timedelta(days=1)
    for kind in SOURCES:
        for month in (now.strftime("%Y%m"), following.strftime("%Y%m")):
            await prepare(engine, kind, month)


async def login_relation(db, start: datetime | None = None, end: datetime | None = None):
    """Read-only union for dashboard queries, optionally pruned to intersecting months."""
    tables = []
    for month in await available_months(db, "login"):
        lower, upper = month_bounds(month)
        if start is not None and upper <= utc_time(start):
            continue
        if end is not None and lower >= utc_time(end):
            continue
        tables.append(month_model("login", month).__table__)
    if not tables:
        # A typed empty relation without reading or creating any physical table.
        from sqlalchemy import literal

        source = LoginLogModel.__table__
        return select(*(literal(None, type_=c.type).label(c.name) for c in source.c)).where(False).subquery()
    return union_all(*(select(table) for table in tables)).subquery()


async def cleanup(engine, days: int = 90) -> dict:
    if days <= 0:
        raise ValueError("日志保留天数必须大于 0")
    cutoff = datetime.now(UTC) - timedelta(days=days)
    stats = {"days": days, "operation_deleted": 0, "login_deleted": 0}
    async with engine.begin() as conn:
        entries = (await conn.execute(select(log_months.c.kind, log_months.c.month).where(log_months.c.kind.in_(tuple(SOURCES))))).all()
        for kind, month in entries:
            table = month_model(kind, month).__table__
            _, end = month_bounds(month)
            if end <= cutoff:
                count = (await conn.execute(select(func.count()).select_from(table))).scalar_one()
                await conn.run_sync(lambda sync, table=table: table.drop(sync, checkfirst=True))
                await conn.execute(delete(log_months).where(log_months.c.kind == kind, log_months.c.month == month))
            else:
                result = await conn.execute(delete(table).where(table.c.created_time < cutoff))
                count = result.rowcount or 0
            stats[kind + "_deleted"] += count
    return stats
