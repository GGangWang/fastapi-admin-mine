"""Shared versioned registry for physical log tables in the logs database."""

import re
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import Column, Integer, MetaData, String, Table, insert, select, text

metadata = MetaData()
months = Table(
    "sys_log_month",
    metadata,
    Column("kind", String(16), primary_key=True),
    Column("month", String(6), primary_key=True),
    Column("version", Integer, nullable=False),
)
KINDS = frozenset({"login", "operation", "http"})


def validate_month(month: str) -> str:
    if not isinstance(month, str) or not re.fullmatch(r"[0-9]{6}", month):
        raise ValueError("日志月份必须是 YYYYMM")
    datetime.strptime(month, "%Y%m")
    return month


def validate_kind(kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"不支持的日志类型: {kind}")
    return kind


@contextmanager
def ddl_lock(connection):
    """Serialize all log kinds, including creation of their shared directory."""
    dialect = connection.dialect.name
    if dialect == "mysql":
        if connection.execute(text("SELECT GET_LOCK('res_nexus_log_ddl', 30)")).scalar() != 1:
            raise RuntimeError("日志月表建表锁超时")
    elif dialect == "postgresql":
        connection.execute(text("SELECT pg_advisory_xact_lock(724192)"))
    elif dialect == "sqlite":
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    try:
        yield
    finally:
        if dialect == "mysql":
            connection.execute(text("SELECT RELEASE_LOCK('res_nexus_log_ddl')"))


def prepare_month(connection, kind: str, month: str, table: Table, version: int = 1):
    validate_kind(kind)
    validate_month(month)
    with ddl_lock(connection):
        months.create(connection, checkfirst=True)
        current = connection.execute(select(months.c.version).where(months.c.kind == kind, months.c.month == month)).scalar()
        if current is not None and current != version:
            raise RuntimeError("日志月表结构版本不受支持，请先执行迁移")
        table.create(connection, checkfirst=True)
        if current is None:
            if connection.dialect.name == "mysql":
                from sqlalchemy.dialects.mysql import insert as mysql_insert

                statement = mysql_insert(months).values(kind=kind, month=month, version=version)
                connection.execute(statement.on_duplicate_key_update(version=months.c.version))
            else:
                connection.execute(insert(months).values(kind=kind, month=month, version=version))


async def available_months(db, kind: str) -> list[str]:
    validate_kind(kind)
    return list((await db.execute(select(months.c.month).where(months.c.kind == kind).order_by(months.c.month.desc()))).scalars())
