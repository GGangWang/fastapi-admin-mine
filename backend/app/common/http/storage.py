"""Versioned physical monthly HTTP log tables (not ORM application tables)."""

import calendar
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import BigInteger, Column, DateTime, Float, Index, Integer, MetaData, String, Table, Text, insert, select, update
from sqlalchemy.dialects.mysql import LONGTEXT

TZ = ZoneInfo("Asia/Shanghai")
metadata = MetaData()
months = Table("sys_http_log_month", metadata, Column("month", String(6), primary_key=True), Column("version", Integer, nullable=False))


def validate_month(month: str) -> str:
    if not re.fullmatch(r"[0-9]{6}", month):
        raise ValueError("日志月份必须是 YYYYMM")
    datetime.strptime(month, "%Y%m")
    return month


def month_table(month: str) -> Table:
    name = "sys_http_log_" + validate_month(month)
    if name in metadata.tables:
        return metadata.tables[name]
    body_type = Text().with_variant(LONGTEXT(), "mysql")
    table = Table(
        name,
        metadata,
        Column("id", String(32), primary_key=True),
        Column("started_at", DateTime, nullable=False),
        Column("service", String(64)),
        Column("business", String(255)),
        Column("operator", String(128)),
        Column("correlation_id", String(128)),
        Column("call_id", String(32)),
        Column("attempt", Integer),
        Column("method", String(16)),
        Column("url", Text),
        Column("status_code", Integer),
        Column("result", String(24)),
        Column("duration_ms", Float),
        Column("first_response_ms", Float),
        Column("request_bytes", BigInteger),
        Column("response_bytes", BigInteger),
        Column("request_headers", body_type),
        Column("response_headers", body_type),
        Column("request_body", body_type),
        Column("response_body", body_type),
        Column("request_body_state", String(24)),
        Column("response_body_state", String(24)),
        Column("error", Text),
    )
    Index(name + "_time", table.c.started_at, table.c.id)
    Index(name + "_trace", table.c.correlation_id)
    return table


def prepare_month(connection, month: str):
    months.create(connection, checkfirst=True)
    table = month_table(month)
    table.create(connection, checkfirst=True)
    # Concurrent creators may both pass checkfirst. The caller serializes DDL
    # using the engine-specific advisory lock below.
    version = connection.execute(select(months.c.version).where(months.c.month == month)).scalar()
    if version is None:
        if connection.dialect.name == "mysql":
            from sqlalchemy.dialects.mysql import insert as mysql_insert

            statement = mysql_insert(months).values(month=month, version=1)
            connection.execute(statement.on_duplicate_key_update(version=months.c.version))
        else:
            connection.execute(insert(months).values(month=month, version=1))
    elif version != 1:
        raise RuntimeError("HTTP 日志月表结构版本不受支持，请先执行迁移")


def prepare_locked(connection, month: str):
    from sqlalchemy import text

    dialect = connection.dialect.name
    if dialect == "mysql":
        if connection.execute(text("SELECT GET_LOCK('res_nexus_http_log_ddl', 30)")).scalar() != 1:
            raise RuntimeError("HTTP 日志月表建表锁超时")
    elif dialect == "postgresql":
        connection.execute(text("SELECT pg_advisory_xact_lock(724191)"))
    try:
        prepare_month(connection, month)
    finally:
        if dialect == "mysql":
            connection.execute(text("SELECT RELEASE_LOCK('res_nexus_http_log_ddl')"))


def initial_months():
    now = datetime.now(TZ)
    following = now.replace(day=calendar.monthrange(now.year, now.month)[1])
    from datetime import timedelta

    return now.strftime("%Y%m"), (following + timedelta(days=1)).strftime("%Y%m")


async def prepare(engine, month):
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: prepare_locked(conn, month))


async def persist(engine, record, bodies):
    table = month_table(record["started_at"].strftime("%Y%m"))
    await prepare(engine, record["started_at"].strftime("%Y%m"))
    # Metadata survives a body write exceeding the DB packet/capacity limit.
    async with engine.begin() as conn:
        await conn.execute(insert(table).values(**record))
    for side, content in bodies.items():
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    update(table)
                    .where(table.c.id == record["id"])
                    .values(
                        {
                            side + "_body": content,
                            side + "_body_state": "recorded",
                        }
                    )
                )
        except Exception as exc:
            async with engine.begin() as conn:
                await conn.execute(update(table).where(table.c.id == record["id"]).values({side + "_body_state": "failed"}))
            from app.core.logger import logger

            logger.error("HTTP body persistence failed id={} side={} error={}", record["id"], side, type(exc).__name__)
