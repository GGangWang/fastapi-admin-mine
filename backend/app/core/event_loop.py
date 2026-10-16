"""Event loop selection for psycopg asynchronous connections on Windows."""

import asyncio
import sys

from sqlalchemy.engine import make_url

from app.config.setting import settings


def requires_selector_loop() -> bool:
    urls = [settings.ASYNC_DB_URI]
    urls.extend(source.async_url.get_secret_value() for source in settings.DATASOURCES.values() if source.async_url)
    return sys.platform == "win32" and any(make_url(url).get_driver_name() in {"psycopg", "psycopg_async"} for url in urls)


def database_event_loop():
    return asyncio.SelectorEventLoop() if requires_selector_loop() else asyncio.new_event_loop()
