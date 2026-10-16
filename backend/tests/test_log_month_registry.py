"""Shared log registry: kind isolation, retention safety, versions and concurrent DDL."""

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, inspect, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.common.http.storage import month_table
from app.common.http.storage import prepare as prepare_http
from app.common.log_month import available_months, months
from app.modules.system.http_log.service import HttpLogService
from app.modules.system.log.storage import cleanup, month_model
from app.modules.system.log.storage import prepare as prepare_audit


def test_shared_registry_and_retention(tmp_path):
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "shared.db"), connect_args={"timeout": 30})
        # All kinds race to create the same registry, including duplicate creators.
        await asyncio.gather(*(prepare_audit(engine, kind, "200001") for kind in ("login", "operation", "login")), prepare_http(engine, "200001"), prepare_http(engine, "200001"))
        await prepare_http(engine, "200002")
        await prepare_audit(engine, "login", "200003")
        http = month_table("200001")
        async with engine.begin() as conn:
            await conn.execute(insert(http).values(id="a" * 32, started_at=datetime(2000, 1, 1), response_body="keep", response_body_state="recorded"))
            await conn.execute(insert(month_model("login", "200001").__table__).values(username="old", created_time=datetime(2000, 1, 1, tzinfo=UTC)))
        async with async_sessionmaker(engine)() as db:
            assert await available_months(db, "login") == ["200003", "200001"]
            assert await available_months(db, "operation") == ["200001"]
            assert await HttpLogService(db).available_months() == ["200002", "200001"]
            assert len((await db.execute(select(months).where(months.c.month == "200001"))).all()) == 3
        result = await cleanup(engine, 90)
        assert result["login_deleted"] == 1
        async with engine.connect() as conn:
            names = await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert "sys_log_month" in names
            assert not {"sys_audit_log_month", "sys_http_log_month", "sys_login_log_200001", "sys_operation_log_200001"} & set(names)
            assert (await conn.execute(select(http.c.response_body))).scalar_one() == "keep"
            assert await available_months(conn, "http") == ["200002", "200001"]
            assert await available_months(conn, "login") == []
        await engine.dispose()

    asyncio.run(scenario())


def test_versions_are_independent_and_rejected_before_creation(tmp_path):
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "versions.db"))
        await prepare_http(engine, "202610")
        async with engine.begin() as conn:
            await conn.execute(update(months).where(months.c.kind == "http", months.c.month == "202610").values(version=9))
            await conn.execute(insert(months).values(kind="login", month="202610", version=9))
        with pytest.raises(RuntimeError, match="版本"):
            await prepare_http(engine, "202610")
        with pytest.raises(RuntimeError, match="版本"):
            await prepare_audit(engine, "login", "202610")
        await prepare_audit(engine, "operation", "202610")
        async with engine.connect() as conn:
            assert not await conn.run_sync(lambda c: inspect(c).has_table("sys_login_log_202610"))
            assert (await conn.execute(select(months.c.version).where(months.c.kind == "operation"))).scalar_one() == 2
            with pytest.raises(ValueError, match="类型"):
                await available_months(conn, "unknown")
        await engine.dispose()

    asyncio.run(scenario())
