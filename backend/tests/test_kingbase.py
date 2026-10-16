"""Offline Kingbase PG-compatible wiring; these tests do not certify a Kingbase server."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from sqlalchemy import Boolean, Column, Integer, MetaData, Table
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateIndex, CreateTable

from app.common.database_types import is_postgres_compatible, sql_dialect
from app.config.setting import Settings, settings
from app.core import database
from app.core.base_schema import AuthSchema
from app.core.database import DatabaseManager
from app.utils.common_util import SqlalchemyUtil


def kingbase_settings():
    return Settings(
        _env_file=None,
        DATABASE_TYPE="kingbase",
        DATABASE_HOST="127.0.0.1",
        DATABASE_PORT=54321,
        DATABASE_USER="user@name",
        DATABASE_PASSWORD="p@ss:/?# +%",
        DATABASE_NAME="res-nexus",
        DATASOURCES={"logs": {"database": "res-nexus-log"}},
    )


def test_configuration_and_url_escaping():
    config = kingbase_settings()
    assert config.DB_URI == config.ASYNC_DB_URI
    for value in (config.DB_URI, config.ASYNC_DB_URI):
        url = make_url(value)
        assert url.drivername == "postgresql+psycopg"
        assert (url.username, url.password, url.port, url.database) == (config.DATABASE_USER, config.DATABASE_PASSWORD, 54321, "res-nexus")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, DATABASE_TYPE="unknown")


def test_sync_async_and_inherited_log_source(monkeypatch):
    pytest.importorskip("psycopg")
    config = kingbase_settings()
    monkeypatch.setattr(database, "settings", config)
    manager = DatabaseManager()
    sync = manager.sync_engine()
    async_engine = manager.engine()
    logs = manager.engine("logs")
    assert sync.dialect.name == async_engine.dialect.name == logs.dialect.name == "postgresql"
    assert sync.dialect.driver == "psycopg" and not sync.dialect.is_async
    assert async_engine.dialect.is_async
    assert logs.url.database == "res-nexus-log" and logs is not async_engine
    assert logs.url.password == config.DATABASE_PASSWORD
    asyncio.run(manager.dispose())


def test_mysql_with_explicit_kingbase_business_source(monkeypatch):
    pytest.importorskip("psycopg")
    config = Settings(
        _env_file=None,
        DATABASE_TYPE="mysql",
        DATASOURCES={
            "logs": {"database": "res-nexus-log"},
            "business": {"async_url": "postgresql+psycopg://u:p@localhost:54321/business", "sync_url": "postgresql+psycopg://u:p@localhost:54321/business"},
        },
    )
    monkeypatch.setattr(database, "settings", config)
    manager = DatabaseManager()
    assert make_url(manager.url()).get_backend_name() == "mysql"
    assert manager.engine("business").dialect.is_async
    assert manager.sync_engine("business").dialect.driver == "psycopg"
    asyncio.run(manager.dispose())


def test_missing_driver_fails_without_credentials(monkeypatch):
    error = ModuleNotFoundError("driver missing", name="psycopg")
    monkeypatch.setattr(database, "create_engine", Mock(side_effect=error))
    monkeypatch.setattr(database, "create_async_engine", Mock(side_effect=error))
    url = "postgresql+psycopg://secret_user:secret_password@localhost/test"
    for create in (database.create_sync_engine, database.create_async_engine_and_session):
        with pytest.raises(RuntimeError, match="uv sync --extra kingbase") as caught:
            create(url)
        assert "secret_password" not in str(caught.value)


def test_postgres_defaults_and_sql_parser():
    import sqlglot

    assert is_postgres_compatible("kingbase") and sql_dialect("kingbase") == "postgres"
    table = Table("flags", MetaData(), Column("id", Integer, primary_key=True), Column("enabled", Boolean, server_default=SqlalchemyUtil.get_boolean_server_default("kingbase", True)))
    ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
    assert "DEFAULT true" in ddl and "SERIAL" in ddl
    assert SqlalchemyUtil.get_server_default_null("kingbase") is not None
    assert sqlglot.parse_one("CREATE TABLE demo (id INTEGER, enabled BOOLEAN)", dialect=sql_dialect("kingbase")).sql(dialect="postgres")


def test_generator_uses_pg_catalog(monkeypatch):
    from app.modules.generator.gencode.crud import GenTableCRUD

    monkeypatch.setattr(settings, "DATABASE_TYPE", "kingbase")
    db = AsyncMock()
    total = Mock()
    total.scalar.return_value = 1
    rows = Mock()
    rows.fetchall.return_value = [("demo", "测试表")]
    db.execute.side_effect = [total, rows]
    result, count = asyncio.run(GenTableCRUD(AuthSchema(), db).get_db_table_page("demo", None))
    assert count == 1 and result[0]["table_type"] == "kingbase"
    assert all("pg_catalog" in str(call.args[0]) for call in db.execute.await_args_list)


def test_ai_database_selection(monkeypatch):
    from app.modules.ai.chat import crud

    monkeypatch.setattr(settings, "DATABASE_TYPE", "kingbase")
    monkeypatch.setattr(crud, "_db_instance", None)
    factory = Mock()
    monkeypatch.setattr(crud, "AsyncPostgresDb", factory)
    assert crud._get_agno_db() is factory.return_value
    assert make_url(factory.call_args.kwargs["db_url"]).drivername == "postgresql+psycopg"
    assert factory.call_args.kwargs["db_schema"] == "public"


def test_models_and_month_tables_compile():
    from app.common.http.storage import month_table
    from app.common.log_month import months
    from app.core.base_model import MappedBase
    from app.modules.system.log.storage import month_model
    from app.utils.import_util import ImportUtil

    ImportUtil.find_models(MappedBase)
    tables = [*MappedBase.metadata.tables.values(), months, month_table("202610"), month_model("login", "202610").__table__, month_model("operation", "202610").__table__]
    for table in tables:
        assert str(CreateTable(table).compile(dialect=postgresql.dialect()))
        for index in table.indexes:
            assert str(CreateIndex(index).compile(dialect=postgresql.dialect()))


def test_windows_loop_selection(monkeypatch):
    from app.core import event_loop

    monkeypatch.setattr(settings, "DATABASE_TYPE", "kingbase")
    monkeypatch.setattr(event_loop.sys, "platform", "win32")
    assert event_loop.requires_selector_loop()
    loop = event_loop.database_event_loop()
    assert isinstance(loop, asyncio.SelectorEventLoop)
    loop.close()


def test_http_body_uses_pg_functions():
    from app.common.http.storage import month_table
    from app.modules.system.http_log.service import HttpLogService

    db = AsyncMock()
    db.bind.dialect.name = "postgresql"
    result = Mock()
    result.mappings.return_value.first.return_value = {"chunk": "中文".encode(), "size": 6, "state": "recorded"}
    db.execute.return_value = result
    service = HttpLogService(db)
    service.table = AsyncMock(return_value=month_table("202610"))
    body = asyncio.run(service.body("202610", "a" * 32, "response"))
    assert body["text"] == "中文"
    sql = str(db.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "convert_to" in sql and "octet_length" in sql


def test_kingbase_type_mapping_on_clean_import():
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = os.environ.copy()
    env["DATABASE_TYPE"] = "kingbase"
    code = """from app.common.constant import GenConstant
from app.modules.generator.gencode.template_safety import pick_sqlalchemy_type
assert 'character varying' in GenConstant.COLUMNTYPE_STR
assert pick_sqlalchemy_type('jsonb', db_type='kingbase') == 'JSONB'
assert pick_sqlalchemy_type('boolean', db_type='kingbase') == 'Boolean'
"""
    result = subprocess.run([sys.executable, "-c", code], env=env, cwd=Path(__file__).parents[1], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
