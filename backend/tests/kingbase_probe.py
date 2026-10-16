"""Run only against explicitly named dedicated Kingbase test databases."""

import asyncio
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, func, insert, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    if os.getenv("KINGBASE_RUN_INTEGRATION") != "1":
        raise RuntimeError("Set KINGBASE_RUN_INTEGRATION=1 explicitly")
    urls = [os.environ["KINGBASE_TEST_URL"], os.environ["KINGBASE_TEST_LOG_URL"]]
    for value in urls:
        url = make_url(value)
        if url.drivername != "postgresql+psycopg" or not url.database or not url.database.endswith("_test"):
            raise RuntimeError("Use postgresql+psycopg URLs and dedicated database names ending in _test")
    if make_url(urls[0]).set(password=None) == make_url(urls[1]).set(password=None):
        raise RuntimeError("Main and log test databases must differ")
    # Keep any imported app globals confined to the explicit test database too.
    url = make_url(urls[0])
    os.environ.update(
        DATABASE_TYPE="kingbase",
        DATABASE_HOST=url.host or "localhost",
        DATABASE_PORT=str(url.port or 54321),
        DATABASE_USER=url.username or "",
        DATABASE_PASSWORD=url.password or "",
        DATABASE_NAME=url.database,
        DATASOURCES=__import__("json").dumps({"logs": {"async_url": urls[1]}}),
    )
    from app.core.logger import logger

    logger.remove()
    from app.common.http.storage import month_table, persist
    from app.common.log_month import months
    from app.core.base_model import MappedBase
    from app.modules.system.log.storage import initialize
    from app.utils.import_util import ImportUtil

    ImportUtil.find_models(MappedBase)
    schema = "kingbase_probe_" + uuid.uuid4().hex
    syncs = [create_engine(value, connect_args={"connect_timeout": 10}) for value in urls]
    asyncs = []
    created = []
    try:
        print("Probe stage: synchronous connection and private schemas")
        for engine in syncs:
            with engine.begin() as conn:
                conn.exec_driver_sql('CREATE SCHEMA "' + schema + '"')
            created.append(engine)
        for value in urls:
            asyncs.append(create_async_engine(value, connect_args={"connect_timeout": 10, "options": "-csearch_path=" + schema}))

        async def probe():
            primary, logs = asyncs
            print("Probe stage: application DDL and PostgreSQL capabilities")
            async with primary.begin() as conn:
                await conn.run_sync(MappedBase.metadata.create_all)
                # Exercise Inspector and catalog/function capabilities required by the framework.
                assert await conn.run_sync(lambda c: inspect(c).get_columns("sys_user"))
                await conn.execute(text("SELECT c.relname FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace LIMIT 1"))
                assert (await conn.execute(text("SELECT octet_length(convert_to('中文', 'UTF8'))"))).scalar_one() == 6
                await conn.execute(text("SELECT pg_advisory_xact_lock(724192)"))
            table = Table("transaction_probe", MetaData(), Column("id", Integer, primary_key=True), Column("value", String(50)))
            async with primary.begin() as conn:
                await conn.run_sync(table.metadata.create_all)
                assert (await conn.execute(insert(table).values(value="中文").returning(table.c.id))).scalar_one() > 0
            from alembic.migration import MigrationContext
            from alembic.operations import Operations

            def migrate(conn):
                operations = Operations(MigrationContext.configure(conn))
                operations.add_column("transaction_probe", Column("extra", String(20)))
                assert "extra" in {column["name"] for column in inspect(conn).get_columns("transaction_probe")}
                operations.drop_column("transaction_probe", "extra")

            print("Probe stage: Alembic DDL and transactions")
            async with primary.begin() as conn:
                await conn.run_sync(migrate)
            factory = async_sessionmaker(primary)
            try:
                async with factory() as db, db.begin():
                    await db.execute(insert(table).values(value="rollback"))
                    raise ValueError("rollback")
            except ValueError:
                pass
            async with factory() as db:
                assert (await db.execute(select(func.count()).select_from(table))).scalar_one() == 1
            print("Probe stage: log registry and HTTP bodies")
            await initialize(logs)
            from datetime import datetime

            month = datetime.now().strftime("%Y%m")
            # Physical month selection follows the explicit occurrence timestamp.
            await persist(logs, {"id": "a" * 32, "started_at": datetime.now(), "response_body_state": "pending"}, {"response": "中文"})
            async with logs.connect() as conn:
                assert (await conn.execute(select(month_table(month).c.response_body))).scalar_one() == "中文"
                assert (await conn.execute(select(months).where(months.c.kind == "http"))).first()
            # Exercise the same PostgreSQL AI storage in the private schema.
            from agno.db.postgres import AsyncPostgresDb

            print("Probe stage: AI table initialization")
            ai = AsyncPostgresDb(db_engine=primary, db_schema=schema, create_schema=False)
            await ai._create_all_tables()
            async with primary.connect() as conn:
                assert await conn.run_sync(lambda c: inspect(c).has_table("agno_sessions"))

        async def run():
            try:
                await probe()
            finally:
                for engine in asyncs:
                    await engine.dispose()

        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop if sys.platform == "win32" else asyncio.new_event_loop) as runner:
            runner.run(run())
        print("PASS: driver, DDL, Inspector, catalog/functions, CRUD/rollback, log registry/body, AI initialization")
    finally:
        for engine in created:
            with engine.begin() as conn:
                conn.exec_driver_sql('DROP SCHEMA "' + schema + '" CASCADE')
        for engine in syncs:
            engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Deliberately exclude exception text and connection URLs.
        print("Kingbase probe failed:", type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
