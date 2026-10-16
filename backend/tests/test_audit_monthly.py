"""Monthly audit storage: rollover, migration safety, query isolation and retention."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, insert, inspect, select
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateTable

from app.core.base_model import MappedBase
from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.modules.system.log.model import LoginLogModel, OperationLogModel
from app.modules.system.log.schema import LoginLogQueryParam
from app.modules.system.log.service import LoginLogService, OperationLogService
from app.modules.system.log.storage import (
    TZ,
    available_months,
    checked_month,
    cleanup,
    login_relation,
    metadata,
    month_bounds,
    month_model,
    prepare,
    record_month,
)
from app.scripts.migrate_audit_logs import migrate


def run(test):
    asyncio.run(test())


def log_id(value):
    return f"{value:032x}"


def login(id, when, username="alice", **extra):
    return dict(id=log_id(id), uuid=f"login-{id}", username=username, status=1, created_time=when, updated_time=when, is_deleted=False, **extra)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-10-31T15:59:59+00:00", "202610"),
        ("2026-10-31T16:00:00+00:00", "202611"),
        ("2026-12-31T16:00:00+00:00", "202701"),
        ("2026-10-31T16:00:00", "202611"),
    ],
)
def test_beijing_month(value, expected):
    assert record_month(datetime.fromisoformat(value)) == expected


@pytest.mark.parametrize("value", ["202613", "202600", "202610x", "2026-10", "202610;DROP", "000001"])
def test_invalid_month(value):
    with pytest.raises(CustomException):
        checked_month(value)


def test_metadata_and_ddl():
    for kind in ("login", "operation"):
        for month in ("202610", "202611"):
            table = month_model(kind, month).__table__
            assert table.metadata is metadata
            assert table.name not in MappedBase.metadata.tables
            assert table.primary_key.name == "pk_" + table.name
            assert all(index.name.startswith(table.name) for index in table.indexes)
            for dialect in (mysql.dialect(), postgresql.dialect(), sqlite.dialect()):
                assert table.name in str(CreateTable(table).compile(dialect=dialect))


def test_migration_queries_and_id_collision(tmp_path):
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "migration.db"))
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: LoginLogModel.__table__.create(c))
            await conn.run_sync(lambda c: OperationLogModel.__table__.create(c))
            await conn.execute(
                insert(LoginLogModel.__table__),
                [
                    login(31, datetime(2026, 10, 31, 15, 59, 59, tzinfo=UTC)),
                    login(32, datetime(2026, 10, 31, 16, tzinfo=UTC), description="retained"),
                ],
            )
        result = await migrate(engine, batch_size=1)
        assert result["login"]["months"] == {"202610": 1, "202611": 1}
        assert result["login"]["inserted"] == 2
        assert (await migrate(engine, 1))["login"]["inserted"] == 0
        november = month_model("login", "202611").__table__
        async with engine.begin() as conn:
            await conn.execute(insert(november), login(31, datetime(2026, 11, 2, tzinfo=UTC), username="bob", description="same ID other month"))
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            assert await available_months(db, "login") == ["202611", "202610"]
            old = await LoginLogService(AuthSchema(), db, "202610").detail(log_id(31))
            new = await LoginLogService(AuthSchema(), db, "202611").detail(log_id(31))
            assert old.username == "alice" and new.username == "bob"
            result = await LoginLogService(AuthSchema(), db, "202611").page(1, 1, LoginLogQueryParam(username="bob"))
            assert result.total == 1 and result.items[0].username == "bob"
            absent = await LoginLogService(AuthSchema(), db, "202612").page(1, 10)
            assert absent.total == 0
            assert await OperationLogService(AuthSchema(), db, "202612").get_list() == []
            with pytest.raises(CustomException):
                await LoginLogService(AuthSchema(), db, "202612").detail(log_id(31))
            with pytest.raises(CustomException):
                await LoginLogService(AuthSchema(), db, "202611").page(1, 10, LoginLogQueryParam(created_time=["2026-10-01 00:00:00", "2026-10-02 00:00:00"]))
            relation = await login_relation(db, *month_bounds("202611"))
            assert (await db.execute(select(func.count()).select_from(relation))).scalar_one() == 2
            await LoginLogService(AuthSchema(), db, "202611").delete([log_id(31)])
            await db.commit()
            assert (await LoginLogService(AuthSchema(), db, "202610").detail(log_id(31))).username == "alice"
        async with engine.connect() as conn:
            assert not await conn.run_sync(lambda c: inspect(c).has_table("sys_login_log_202612"))
        await engine.dispose()

    run(scenario)


def test_migration_conflict_stops_without_overwrite(tmp_path):
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "conflict.db"))
        await prepare(engine, "login", "202610")
        table = month_model("login", "202610").__table__
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: LoginLogModel.__table__.create(c))
            await conn.execute(insert(LoginLogModel.__table__), login(1, datetime(2026, 10, 2, tzinfo=UTC)))
            bad = login(1, datetime(2026, 10, 2, tzinfo=UTC), username="other")
            bad["uuid"] = "other-record"
            await conn.execute(insert(table), bad)
        with pytest.raises(RuntimeError, match="迁移冲突"):
            await migrate(engine)
        async with engine.connect() as conn:
            assert (await conn.execute(select(table.c.username))).scalar_one() == "other"
        await engine.dispose()

    run(scenario)


def test_concurrent_prepare_and_delayed_write(tmp_path, monkeypatch):
    async def scenario():
        from app.core import database
        from app.modules.system.log.crud import LoginLogCRUD

        engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "concurrent.db"), connect_args={"timeout": 30})
        monkeypatch.setattr(database, "async_engine", engine)
        await asyncio.gather(*(prepare(engine, "login", "202612") for _ in range(6)))
        factory = async_sessionmaker(engine)
        async with factory() as db:
            assert await available_months(db, "login") == ["202612"]
        async with factory() as db, db.begin():
            obj = await LoginLogCRUD(AuthSchema(), db, "202612").create(
                {
                    "username": "delayed",
                    "created_time": datetime(2026, 10, 31, 16, tzinfo=UTC),
                }
            )
            assert obj.__table__.name == "sys_login_log_202611"
        async with factory() as db:
            assert (await LoginLogService(AuthSchema(), db, "202611").page(1, 10)).total == 1
        await engine.dispose()

    run(scenario)


def test_retention_drop_and_boundary(tmp_path):
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "retention.db"))
        cutoff = datetime.now(UTC) - timedelta(days=90)
        old = cutoff - timedelta(days=60)
        boundary_old = cutoff - timedelta(seconds=2)
        recent = cutoff + timedelta(seconds=5)
        for when in (old, boundary_old, recent):
            await prepare(engine, "login", record_month(when))
        async with engine.begin() as conn:
            for id, when in enumerate((old, boundary_old, recent), 1):
                await conn.execute(insert(month_model("login", record_month(when)).__table__), login(id, when))
        result = await cleanup(engine, 90)
        assert result == {"days": 90, "operation_deleted": 0, "login_deleted": 2}
        async with engine.connect() as conn:
            assert not await conn.run_sync(lambda c: inspect(c).has_table(month_model("login", record_month(old)).__table__.name))
            relation = await login_relation(conn)
            assert (await conn.execute(select(func.count()).select_from(relation))).scalar_one() == 1
        with pytest.raises(ValueError):
            await cleanup(engine, 0)
        await engine.dispose()

    run(scenario)


def test_query_model_month_and_filters():
    from typing import Annotated

    from fastapi import Depends, FastAPI, Query
    from fastapi.testclient import TestClient

    app = FastAPI()
    from app.modules.system.log.controller import login_search_params

    @app.get("/probe")
    def probe(month: Annotated[str, Query()], search: Annotated[LoginLogQueryParam, Depends(login_search_params)]):
        return {"month": month, "username": search.username}

    response = TestClient(app).get("/probe", params={"month": "202610", "username": "alice"})
    assert response.status_code == 200, response.text
    assert response.json()["username"] == "alice"


def test_dashboard_beijing_days_across_months(tmp_path, monkeypatch):
    async def scenario():
        from unittest.mock import AsyncMock

        from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, Table
        from sqlalchemy.orm import registry

        from app.modules.monitor.online import service as online

        engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "dashboard.db"))
        log_engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "dashboard-logs.db"))
        await prepare(log_engine, "login", "202610")
        await prepare(log_engine, "login", "202611")
        user_meta = MetaData()
        users = Table("dashboard_test_users", user_meta, Column("id", Integer, primary_key=True), Column("created_time", DateTime(timezone=True)), Column("is_deleted", Boolean))

        class User:
            pass

        registry(metadata=user_meta).map_imperatively(User, users)
        monkeypatch.setattr(online, "UserModel", User)

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 11, 1, 12, tzinfo=TZ).astimezone(tz or UTC)

        monkeypatch.setattr(online, "datetime", Clock)
        monkeypatch.setattr(online.OnlineService, "get_online_list", AsyncMock(return_value=[]))
        async with engine.begin() as conn:
            await conn.run_sync(user_meta.create_all)
            await conn.execute(insert(users).values(id=1, created_time=datetime(2026, 10, 31, 17, tzinfo=UTC), is_deleted=False))
        async with log_engine.begin() as conn:
            for id, when in enumerate((datetime(2026, 10, 31, 15, 59, 59, tzinfo=UTC), datetime(2026, 10, 31, 16, tzinfo=UTC), datetime(2026, 11, 1, 3, tzinfo=UTC)), 1):
                await conn.execute(insert(month_model("login", record_month(when)).__table__), login(id, when))
        async with async_sessionmaker(engine)() as db, async_sessionmaker(log_engine)() as log_db:
            stats = await online.OnlineService.get_dashboard_stats(db, None, log_db)
            assert stats.today_login_count == 2 and stats.today_unique_users == 1
            assert len(stats.login_trend) == 7
            assert stats.login_trend[-1].day == "2026-11-01"
            assert stats.login_trend[-1].logins == 2 and stats.login_trend[-1].new_users == 1
            assert stats.login_trend[-2].logins == 1
            assert len(stats.recent_logins) == 3
        await engine.dispose()
        await log_engine.dispose()

    run(scenario)


def test_operation_delayed_write(tmp_path, monkeypatch):
    async def scenario():
        from app.core import database, router_class

        engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "operation.db"))
        monkeypatch.setattr(database, "async_engine", engine)
        monkeypatch.setattr(database.databases, "factory", lambda name="default": async_sessionmaker(engine))
        monkeypatch.setattr(database.databases, "engine", lambda name="default": engine)
        await router_class._write_operation_log_async(
            {
                "created_time": datetime(2026, 12, 31, 16, tzinfo=UTC),
                "username": "operator",
                "request_path": "/delayed",
                "request_method": "POST",
                "response_code": 200,
            }
        )
        async with async_sessionmaker(engine)() as db:
            result = await OperationLogService(AuthSchema(), db, "202701").page(1, 10)
            assert result.total == 1 and result.items[0].request_path == "/delayed"
            assert (await OperationLogService(AuthSchema(), db, "202612").page(1, 10)).total == 0
        await engine.dispose()

    run(scenario)


def test_authenticated_log_month_api(test_client, auth_headers):
    for kind in ("login", "operation"):
        base = f"/system/log/{kind}"
        response = test_client.get(base + "/months", headers=auth_headers)
        assert response.status_code == 200, response.text
        assert isinstance(response.json()["data"], list)
        assert test_client.get(base + "/list", headers=auth_headers).status_code == 422
        invalid = test_client.get(base + "/list", params={"month": "202613"}, headers=auth_headers)
        assert invalid.status_code == 400, invalid.text
        empty = test_client.get(base + "/list", params={"month": "209912"}, headers=auth_headers)
        assert empty.status_code == 200, empty.text
        assert empty.json()["data"]["total"] == 0
    month = datetime.now(TZ).strftime("%Y%m")
    response = test_client.get("/system/log/login/list", params={"month": month, "username": "admin", "page_no": 1, "page_size": 10}, headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["total"] >= 1
    log_id = response.json()["data"]["items"][0]["id"]
    detail = test_client.get(f"/system/log/login/detail/{log_id}", params={"month": month}, headers=auth_headers)
    assert detail.status_code == 200 and detail.json()["data"]["username"] == "admin"
    exported = test_client.post("/system/log/operation/export", params={"month": "209912"}, json={}, headers=auth_headers)
    assert exported.status_code == 200 and exported.content.startswith(b"PK")


def test_retention_builtin_runs_without_code_exec(monkeypatch):
    from unittest.mock import AsyncMock

    from app.core.ap_scheduler import SchedulerUtil
    from app.modules.task.cronjob.node.handlers import audit_log_cleanup as handler_module

    expected = {"days": 90, "operation_deleted": 0, "login_deleted": 0}
    cleanup_mock = AsyncMock(return_value=expected)
    monkeypatch.setattr(handler_module, "cleanup", cleanup_mock)
    handler = SchedulerUtil.resolve_builtin_handler("builtin:audit_log_cleanup")
    assert handler(days=90) == expected
    cleanup_mock.assert_awaited_once()
