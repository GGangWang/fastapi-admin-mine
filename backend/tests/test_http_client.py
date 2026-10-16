import asyncio
import json
from datetime import datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.common.http import HttpClient, http_context, iter_ndjson, iter_sse
from app.common.http.logging import writer
from app.common.http.storage import month_table, persist, prepare
from app.modules.system.http_log.service import HttpLogService


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk

    async def aclose(self):
        self.closed = True


def test_json_capture_and_independent_switches(monkeypatch):
    async def run():
        events = []

        def submit(record, captures, encoding):
            events.append((record, {side: capture.read() if capture.enabled else None for side, capture in captures.items()}))
            for capture in captures.values():
                capture.cleanup()

        monkeypatch.setattr(writer, "submit", submit)

        async def handler(request):
            await request.aread()
            return httpx.Response(200, headers={"content-type": "application/json"}, stream=Chunks(['{"secret":"密钥"}'.encode()]))

        client = HttpClient(transport=httpx.MockTransport(handler))
        with http_context(operator="admin"):
            assert await client.post_json("https://example.test", json={"password": "plain"}) == {"secret": "密钥"}
        assert events[0][0]["operator"] == "admin"
        assert json.loads(events[0][1]["request"])["password"] == "plain"
        assert events[0][1]["response"] == '{"secret":"密钥"}'
        await client.post_json("https://example.test", json={}, log_request_body=False)
        assert events[1][1]["request"] is None and events[1][1]["response"]
        await client.close()

    asyncio.run(run())


def test_stream_does_not_preread_and_closes(monkeypatch):
    async def run():
        events = []
        source = Chunks([b"first", b"second"])

        def submit(record, captures, encoding):
            events.append(record)
            assert not captures["response"].enabled
            for capture in captures.values():
                capture.cleanup()

        monkeypatch.setattr(writer, "submit", submit)
        client = HttpClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=source)))
        async with client.stream("GET", "https://example.test") as response:
            assert events == []
            async for chunk in response.aiter_bytes():
                assert chunk == b"first"
                break
        assert source.closed
        assert len(events) == 1 and events[0]["result"] == "closed"
        await client.close()

    asyncio.run(run())


def test_protocol_boundaries():
    async def run():
        data = ": ping\r\nevent: token\r\ndata: 中\r\ndata: 文\r\n\r\ndata: [DONE]\n\n".encode()

        async def pieces(raw):
            for value in raw:
                yield bytes([value])

        result = [item async for item in iter_sse(pieces(data))]
        assert result == [{"event": "token", "data": "中\n文"}, {"data": "[DONE]"}]
        assert [item async for item in iter_sse(pieces(b"data: one\r\rdata: two\r\r"))] == [{"data": "one"}, {"data": "two"}]
        assert [item async for item in iter_ndjson(pieces(b'{"a":1}\n{"a":2}'))] == [{"a": 1}, {"a": 2}]

    asyncio.run(run())


def test_single_month_and_utf8_body_paging(tmp_path):
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "logs.db"))
        await prepare(engine, "202610")
        text = "a" * 65535 + "中" + "文" * 100
        record = {
            "id": "a" * 32,
            "started_at": datetime(2026, 10, 31, 23, 59),
            "method": "GET",
            "url": "https://test",
            "result": "success",
            "request_body_state": "not_recorded",
            "response_body_state": "pending",
        }
        await persist(engine, record, {"response": text})
        async with AsyncSession(engine) as db:
            service = HttpLogService(db)
            rows = await service.page("202610")
            assert rows["total"] == 1 and "response_body" not in rows["items"][0]
            assert rows["items"][0]["started_at"] == "2026-10-31 23:59:00"
            assert (await service.page("202610", start_time="2026-10-31 23:00:00", end_time="2026-10-31 23:59:59"))["total"] == 1
            with pytest.raises(Exception, match="时间格式无效"):
                await service.page("202610", start_time="2026-10-31T15:00:00Z")
            first = await service.body("202610", "a" * 32, "response")
            second = await service.body("202610", "a" * 32, "response", first["next_offset"])
            assert first["text"] + second["text"] == text
            assert first["next_offset"] == 65535
            with pytest.raises(Exception, match="所选月份"):
                await service.page("202610", start_time="2026-09-30 23:59:59")
            with pytest.raises(Exception, match="YYYYMM"):
                await service.table("202610;DROP TABLE")
        await engine.dispose()

    asyncio.run(run())


def test_atomic_file_download(tmp_path):
    async def run():
        source = Chunks([b"one", b"two"])
        client = HttpClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=source)))
        target = tmp_path / "文件.txt"
        await client.download_file("POST", "https://test", target, json={"id": 1})
        assert target.read_bytes() == b"onetwo"
        with pytest.raises(FileExistsError):
            await client.download_file("GET", "https://test", target)
        assert list(tmp_path.glob(".res-nexus-download-*")) == []
        await client.close()

    asyncio.run(run())


def test_download_filename_and_sdk_injection():
    from app.common.http.client import download_filename, http_clients
    from app.utils.ai_factory import AgnoFactory

    filename = download_filename({"content-disposition": "attachment; filename*=UTF-8''%E4%B8%AD%E6%96%87.txt"}, "https://test/file")
    assert filename == "中文.txt"
    assert download_filename({"content-disposition": 'attachment; filename="../../safe.txt"'}, "https://test") == "safe.txt"
    team = AgnoFactory().create_agent("100", "team", "session", model_config={"api_key": "test-key"})
    assert team.model.http_client is http_clients.get("ai").raw
    assert team.model.max_retries == 0
    assert team.model.get_async_client().timeout.connect == 10
    assert team.model.get_async_client().timeout.read == 60


def test_proxy_preserves_range_and_raw_encoding(monkeypatch):
    async def run():
        events = []

        def submit(record, captures, encoding):
            events.append(record)
            for capture in captures.values():
                capture.cleanup()

        monkeypatch.setattr(writer, "submit", submit)

        async def handler(request):
            assert request.headers["range"] == "bytes=0-2"
            assert "cookie" not in request.headers
            return httpx.Response(
                206,
                headers={"Content-Range": "bytes 0-2/6", "Content-Length": "3", "Connection": "X-Hop", "X-Hop": "discard", "Content-Disposition": "attachment; filename*=UTF-8''%E4%B8%AD.txt"},
                stream=Chunks([b"abc"]),
            )

        client = HttpClient(transport=httpx.MockTransport(handler))
        response = await client.proxy_stream("GET", "https://test", incoming_headers={"Range": "bytes=0-2", "Cookie": "private"})
        assert response.status_code == 206
        assert "x-hop" not in response.headers
        assert response.headers["content-range"] == "bytes 0-2/6"
        assert b"".join([part async for part in response.body_iterator]) == b"abc"
        assert len(events) == 1
        await client.close()

    asyncio.run(run())


def test_connection_failure_is_logged_without_retry(monkeypatch):
    async def run():
        events = []

        def submit(record, captures, encoding):
            events.append(record)
            for capture in captures.values():
                capture.cleanup()

        monkeypatch.setattr(writer, "submit", submit)

        async def handler(request):
            raise httpx.ConnectTimeout("timeout", request=request)

        client = HttpClient(transport=httpx.MockTransport(handler))
        with pytest.raises(httpx.ConnectTimeout):
            await client.get_json("https://test")
        assert len(events) == 1
        assert events[0]["result"] == "failed" and events[0]["error"] == "ConnectTimeout"
        await client.close()

    asyncio.run(run())


def test_shared_client_does_not_share_authentication():
    async def run():
        seen = []

        async def handler(request):
            seen.append(dict(request.headers))
            return httpx.Response(200, json={}, headers={"set-cookie": "session=user-one; Path=/"})

        client = HttpClient(transport=httpx.MockTransport(handler))
        await client.get_json("https://test", headers={"Authorization": "Bearer first"})
        await client.get_json("https://test", headers={"Authorization": "Bearer second"})
        assert seen[1]["authorization"] == "Bearer second"
        assert "cookie" not in seen[1]
        await client.close()

    asyncio.run(run())


def test_monthly_migration_upgrade_downgrade(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path

    from alembic import op
    from sqlalchemy import create_engine, insert, inspect, select

    from app.core.base_model import MappedBase
    from app.modules.system.menu.model import MenuModel
    from app.modules.system.role.model import RoleMenusModel, RoleModel
    from app.utils.import_util import ImportUtil

    ImportUtil.find_models(MappedBase)
    engine = create_engine("sqlite:///" + str(tmp_path / "migration.db"))
    with engine.begin() as conn:
        for table in (MenuModel.__table__, RoleModel.__table__, RoleMenusModel.__table__):
            table.create(conn)
        system_id = conn.execute(insert(MenuModel.__table__).values(name="系统管理", route_name="System", type=1)).inserted_primary_key[0]
        log_id = conn.execute(insert(MenuModel.__table__).values(name="日志管理", route_name="Log", type=2, parent_id=system_id, permission="module_system:log:query")).inserted_primary_key[0]
        conn.execute(insert(RoleModel.__table__).values(name="超级管理员", code="SUPER_ADMIN"))
        source = Path(__file__).parents[1] / "app/alembic/versions/20261014_http_log.py"
        spec = importlib.util.spec_from_file_location("http_log_revision", source)
        revision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(revision)
        monkeypatch.setattr(op, "get_bind", lambda: conn)
        revision.upgrade()
        revision.upgrade()
        menus = list(conn.execute(select(MenuModel.__table__.c.permission).where(MenuModel.__table__.c.permission.like("system:http_log:%"))).scalars())
        assert len(menus) == 4
        http_parent_ids = conn.execute(select(MenuModel.__table__.c.parent_id).where(MenuModel.__table__.c.permission.like("system:http_log:%"))).scalars().all()
        assert http_parent_ids == [log_id] * 4
        revision.downgrade()
        assert "sys_http_log_month" not in inspect(conn).get_table_names()
        assert conn.execute(select(MenuModel.__table__.c.id).where(MenuModel.__table__.c.route_name == "System")).first()
    engine.dispose()


def test_body_write_failure_preserves_metadata(tmp_path):
    async def run():
        from sqlalchemy import select, text

        engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "failed.db"))
        await prepare(engine, "202610")
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TRIGGER reject_body BEFORE UPDATE OF request_body ON sys_http_log_202610 BEGIN SELECT RAISE(FAIL, 'capacity'); END"))
        record = {"id": "b" * 32, "started_at": datetime(2026, 10, 14), "result": "success", "request_body_state": "pending", "response_body_state": "pending"}
        await persist(engine, record, {"request": "{}", "response": '{"ok":true}'})
        async with engine.connect() as conn:
            table = month_table("202610")
            row = (await conn.execute(select(table).where(table.c.id == record["id"]))).mappings().one()
            assert row["request_body_state"] == "failed"
            assert row["response_body_state"] == "recorded"
            assert row["result"] == "success"
        await engine.dispose()

    asyncio.run(run())


def test_log_api_permission_and_month_validation(tmp_path, monkeypatch):
    async def run():
        from fastapi import FastAPI

        from app.core.base_schema import AuthSchema
        from app.core.dependencies import db_getter, get_current_user, log_db_getter
        from app.core.exceptions import handle_exception
        from app.modules.system.http_log.controller import HttpLogRouter

        engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "api.db"))
        await prepare(engine, "202610")
        app = FastAPI()
        app.include_router(HttpLogRouter)
        handle_exception(app)

        class TicketRedis:
            def __init__(self):
                self.values = {}

            async def set(self, key, value, ex=None):
                self.values[key] = value

            async def getdel(self, key):
                return self.values.pop(key, None)

        app.state.redis = TicketRedis()
        import app.modules.system.http_log.controller as controller

        monkeypatch.setattr(controller.databases, "factory", lambda name="default": lambda: AsyncSession(engine))

        async def db():
            async with AsyncSession(engine) as session:
                yield session

        auth = AuthSchema()
        auth.user.id = 100
        auth.user.is_superuser = False
        app.dependency_overrides[db_getter] = db
        app.dependency_overrides[log_db_getter] = db
        app.dependency_overrides[get_current_user] = lambda: auth
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/http-log/months")).status_code == 403
            auth.permissions = ["system:http_log:query"]
            assert (await client.get("/http-log/months")).json()["data"] == ["202610"]
            result = await client.get("/http-log/list", params={"month": "202610", "end_time": "2026-11-01T00:00:00"})
            assert result.status_code == 400
            assert (await client.get("/http-log/202610/" + "a" * 32)).status_code == 403
            await persist(engine, {"id": "a" * 32, "started_at": datetime(2026, 10, 14), "response_body_state": "pending", "request_body_state": "not_recorded"}, {"response": '{"message":"中文"}'})
            auth.permissions = ["system:http_log:download"]
            issued = await client.post("/http-log/202610/" + "a" * 32 + "/ticket/response")
            assert issued.status_code == 200
            ticket = issued.json()["data"]["ticket"]
            downloaded = await client.get("/http-log/file/" + ticket)
            assert downloaded.text == '{"message":"中文"}'
            assert downloaded.headers["content-disposition"].startswith("attachment;")
            assert (await client.get("/http-log/file/" + ticket)).status_code == 403
            assert (await client.get("/http-log/202610/" + "a" * 32 + "/body/response")).status_code == 403
        await engine.dispose()

    asyncio.run(run())
