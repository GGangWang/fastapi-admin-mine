"""Named sources: isolation, independent rollback, dependencies and metadata ownership."""

import asyncio

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, MetaData, Table, insert, select

from app.config.setting import DataSourceConfig, settings
from app.core.base_model import MappedBase
from app.core.database import DatabaseManager
from app.modules.system.log.model import LogBase


def manager_for(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_TYPE", "sqlite")
    monkeypatch.setattr(settings, "DATABASE_NAME", str(tmp_path / "main.db"))
    monkeypatch.setattr(settings, "DATASOURCES", {"logs": DataSourceConfig(database=str(tmp_path / "logs.db"))})
    return DatabaseManager()


def test_transactions_and_concurrent_sessions(tmp_path, monkeypatch):
    manager = manager_for(tmp_path, monkeypatch)

    async def scenario():
        table = Table("records", MetaData(), Column("id", Integer, primary_key=True))
        for name in ("default", "logs"):
            async with manager.engine(name).begin() as c:
                await c.run_sync(table.metadata.create_all)
        called = []

        async def callback():
            called.append(True)

        async with manager.session() as main:
            await main.execute(insert(table).values(id=1))
            with pytest.raises(RuntimeError):
                async with manager.session("logs") as logs:
                    logs.info["after_commit_callbacks"] = {"failed": callback}
                    await logs.execute(insert(table).values(id=2))
                    raise RuntimeError("rollback logs only")
            main.info["after_commit_callbacks"] = {"committed": callback}
        assert called == [True]
        async with manager.session() as main, manager.session("logs") as logs:
            assert (await main.execute(select(table.c.id))).scalars().all() == [1]
            assert (await logs.execute(select(table.c.id))).scalars().all() == []
        sessions = []

        async def write(id):
            async with manager.session("logs") as db:
                sessions.append(db)
                await db.execute(insert(table).values(id=id))

        await asyncio.gather(*(write(i) for i in range(3, 8)))
        assert len({id(s) for s in sessions}) == 5
        async with manager.session("logs") as logs:
            assert len((await logs.execute(select(table.c.id))).all()) == 5
        assert manager.engine() is not manager.engine("logs")
        await manager.dispose()

    asyncio.run(scenario())


def test_dependency_reuse_and_source_selection(tmp_path, monkeypatch):
    from app.core import dependencies

    manager = manager_for(tmp_path, monkeypatch)
    monkeypatch.setattr(dependencies, "databases", manager)
    default_dep, logs_dep = dependencies.get_db(), dependencies.get_db("logs")
    assert logs_dep is dependencies.get_db("logs")
    app = FastAPI()

    @app.get("/probe")
    async def probe(main=Depends(default_dep), first=Depends(logs_dep), second=Depends(logs_dep)):
        return {"same": first is second, "isolated": main is not first, "main": main.bind.url.database, "logs": first.bind.url.database}

    with TestClient(app) as client:
        value = client.get("/probe").json()
        assert value["same"] and value["isolated"]
        assert value["main"].endswith("main.db") and value["logs"].endswith("logs.db")
    asyncio.run(manager.dispose())


def test_log_metadata_and_unknown_source(tmp_path, monkeypatch):
    manager = manager_for(tmp_path, monkeypatch)
    assert "sys_login_log" in LogBase.metadata.tables
    assert "sys_operation_log" in LogBase.metadata.tables
    assert not {"sys_login_log", "sys_operation_log"} & MappedBase.metadata.tables.keys()
    assert not any(t.foreign_keys for t in LogBase.metadata.tables.values())
    with pytest.raises(ValueError, match="未配置"):
        manager.factory("missing")
    monkeypatch.setattr(settings, "DATASOURCES", {"logs": DataSourceConfig(database=settings.DATABASE_NAME)})
    with pytest.raises(ValueError, match="独立"):
        manager.engine("logs")


def test_log_driver_uses_its_own_url(tmp_path, monkeypatch):
    manager = manager_for(tmp_path, monkeypatch)
    # The main setting can be MySQL while the log source uses SQLite.
    monkeypatch.setattr(settings, "DATABASE_TYPE", "mysql")
    monkeypatch.setattr(settings, "DATASOURCES", {"logs": DataSourceConfig(async_url="sqlite+aiosqlite:///" + str(tmp_path / "other.db"))})

    async def scenario():
        async with manager.engine("logs").connect() as conn:
            assert (await conn.exec_driver_sql("PRAGMA busy_timeout")).scalar() == 30000
        await manager.dispose()

    asyncio.run(scenario())
