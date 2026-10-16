import asyncio
from datetime import UTC, datetime

from sqlalchemy import Integer, MetaData, String, Table, insert, inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.common.log_month import months
from app.common.log_time import http_timestamp
from app.core.base_schema import AuthSchema
from app.modules.system.log.model import LoginLogModel
from app.modules.system.log.schema import LoginLogOutSchema, LogPaginationQueryParam
from app.modules.system.log.service import LoginLogService
from app.modules.system.log.storage import month_model
from app.modules.system.log.upgrade import upgrade_ids


def test_beijing_timezone_transport():
    row = LoginLogOutSchema(id="a" * 32, username="alice", created_time=datetime(2026, 10, 15, 2))
    assert row.model_dump(mode="json")["created_time"] == "2026-10-15 10:00:00"
    assert http_timestamp(datetime(2026, 10, 15, 10)) == "2026-10-15 10:00:00"
    assert LogPaginationQueryParam().order_by == [{"created_time": "desc"}, {"id": "desc"}]


def test_legacy_integer_upgrade_and_new_uuid_write(tmp_path):
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "ids.db"))
        legacy = LoginLogModel.__table__.to_metadata(MetaData(), name="sys_login_log_202610")
        legacy.c.id.type = Integer()
        legacy.c.id.default = None
        legacy.c.id.autoincrement = True
        async with engine.begin() as conn:
            await conn.run_sync(legacy.create)
            await conn.run_sync(months.create)
            await conn.execute(insert(months).values(kind="login", month="202610", version=1))
            await conn.execute(insert(legacy).values(id=7, uuid="a" * 32, username="alice", created_time=datetime(2026, 10, 15, 2, tzinfo=UTC)))
        assert await upgrade_ids(engine) == {legacy.name: 1}
        assert await upgrade_ids(engine) == {}
        async with engine.connect() as conn:
            columns = await conn.run_sync(lambda c: inspect(c).get_columns(legacy.name))
            assert isinstance(next(c for c in columns if c["name"] == "id")["type"], String)
            assert (await conn.execute(select(months.c.version))).scalar_one() == 2
        async with async_sessionmaker(engine)() as db:
            detail = await LoginLogService(AuthSchema(), db, "202610").detail("a" * 32)
            assert detail.username == "alice"
            model = month_model("login", "202610")
            obj = model(username="new", created_time=datetime(2026, 10, 16, tzinfo=UTC))
            db.add(obj)
            await db.flush()
            assert isinstance(obj.id, str) and len(obj.id) == 32 and obj.id != "a" * 32
            result = await LoginLogService(AuthSchema(), db, "202610").page(1, 10)
            assert [row.username for row in result.items] == ["new", "alice"]
            await db.rollback()
        await engine.dispose()

    asyncio.run(run())


def test_menu_merge_preserves_http_only_permissions(monkeypatch):
    from types import SimpleNamespace

    from sqlalchemy import Boolean, Column, create_engine

    from app.modules.system.http_log.menu import install_menu
    from app.modules.system.menu import model as menu_model
    from app.modules.system.role import model as role_model

    meta = MetaData()
    menus = Table(
        "menu_probe",
        meta,
        Column("id", Integer, primary_key=True),
        Column("name", String(64)),
        Column("route_name", String(64)),
        Column("permission", String(100)),
        Column("type", Integer),
        Column("parent_id", Integer),
        Column("route_path", String(100)),
        Column("component_path", String(100)),
        Column("hidden", Boolean),
        Column("is_deleted", Boolean, default=False),
    )
    roles = Table("role_probe", meta, Column("id", Integer, primary_key=True), Column("code", String(64)))
    links = Table("link_probe", meta, Column("role_id", Integer, primary_key=True), Column("menu_id", Integer, primary_key=True))
    monkeypatch.setattr(menu_model, "MenuModel", SimpleNamespace(__table__=menus))
    monkeypatch.setattr(role_model, "RoleModel", SimpleNamespace(__table__=roles))
    monkeypatch.setattr(role_model, "RoleMenusModel", SimpleNamespace(__table__=links))
    engine = create_engine("sqlite://")
    meta.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            insert(menus),
            [
                {"id": 20, "route_name": "Log", "permission": "module_system:log:query", "type": 2},
                {"id": 21, "route_name": None, "permission": "module_system:log:query", "type": 3},
                {"id": 30, "route_name": "HttpLog", "permission": "system:http_log:query", "type": 2},
            ],
        )
        conn.execute(insert(roles), [{"id": 1, "code": "HTTP_ONLY"}, {"id": 2, "code": "OP_ONLY"}])
        conn.execute(insert(links), [{"role_id": 1, "menu_id": 30}, {"role_id": 2, "menu_id": 20}])
        install_menu(conn)
        install_menu(conn)
        http_permissions = list(conn.execute(select(menus.c.permission).join(links, menus.c.id == links.c.menu_id).where(links.c.role_id == 1)).scalars())
        op_permissions = list(conn.execute(select(menus.c.permission).join(links, menus.c.id == links.c.menu_id).where(links.c.role_id == 2)).scalars())
        assert "system:http_log:query" in http_permissions
        assert "module_system:log:query" not in http_permissions
        assert "module_system:log:query" in op_permissions
        assert conn.execute(select(menus.c.id).where(menus.c.route_name == "HttpLog")).first() is None
        assert conn.execute(select(menus.c.parent_id).where(menus.c.id == 30)).scalar_one() == 20
    engine.dispose()
