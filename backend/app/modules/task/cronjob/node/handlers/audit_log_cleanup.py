"""Audit retention handler, runnable with code-block execution disabled."""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import databases
from app.core.event_loop import database_event_loop
from app.modules.system.log.storage import cleanup


def audit_log_cleanup(days: int = 90) -> dict:
    # Scheduler workers use their own event loops; never share pooled async connections.
    async def execute():
        engine = create_async_engine(databases.url("logs"), poolclass=NullPool)
        try:
            return await cleanup(engine, int(days))
        finally:
            await engine.dispose()

    with asyncio.Runner(loop_factory=database_event_loop) as runner:
        return runner.run(execute())
