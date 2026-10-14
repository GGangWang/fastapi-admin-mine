"""Availability migration preserves meaning and leaves independent business states alone."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table, create_engine, inspect, select

spec = importlib.util.spec_from_file_location("enable_status_revision", Path(__file__).parents[1] / "app/alembic/versions/20261014_enable_status.py")
revision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(revision)


def database():
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    user = Table("sys_user", metadata, Column("id", Integer, primary_key=True), Column("status", Integer, nullable=False, server_default="0"), Column("is_deleted", Boolean))
    notice = Table("sys_notice", metadata, Column("id", Integer, primary_key=True), Column("status", Integer))
    dictionary = Table(
        "sys_dict_info",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("status", Integer, nullable=False, server_default="0"),
        Column("parent_id", Integer),
        Column("dict_type", String),
        Column("dict_code", String),
        Column("is_deleted", Boolean),
        Column("active_key", String, unique=True),
    )
    metadata.create_all(engine)
    return engine, user, notice, dictionary


def test_upgrade_downgrade_defaults_deleted_rows_and_business_states():
    engine, user, notice, dictionary = database()
    with engine.begin() as connection:
        connection.execute(user.insert(), [{"id": 1, "status": 0, "is_deleted": False}, {"id": 2, "status": 1, "is_deleted": True}])
        connection.execute(notice.insert(), [{"id": 1, "status": 0}, {"id": 2, "status": 1}, {"id": 3, "status": 2}])
        connection.execute(
            dictionary.insert(),
            [
                {"id": 1, "status": 0, "parent_id": None, "dict_type": "sys_enable_status", "dict_code": "sys_enable_status", "is_deleted": False},
                {"id": 2, "status": 0, "parent_id": 1, "dict_type": "sys_enable_status", "dict_code": "0", "is_deleted": False},
                {"id": 3, "status": 1, "parent_id": 1, "dict_type": "sys_enable_status", "dict_code": "1", "is_deleted": False},
                {"id": 4, "status": 0, "parent_id": 1, "dict_type": "sys_user_sex", "dict_code": "0", "is_deleted": False},
            ],
        )
        with Operations.context(MigrationContext.configure(connection)):
            revision.upgrade()
        assert list(connection.execute(select(user.c.status, user.c.is_deleted).order_by(user.c.id))) == [(1, False), (0, True)]
        assert list(connection.execute(select(notice.c.status).order_by(notice.c.id)).scalars()) == [0, 1, 2]
        assert list(connection.execute(select(dictionary.c.dict_code).order_by(dictionary.c.id)).scalars()) == ["sys_enable_status", "1", "0", "0"]
        assert str(inspect(connection).get_columns("sys_user")[1]["default"]).strip("'") == "1"
        with Operations.context(MigrationContext.configure(connection)):
            revision.downgrade()
        assert list(connection.execute(select(user.c.status, user.c.is_deleted).order_by(user.c.id))) == [(0, False), (1, True)]
        assert list(connection.execute(select(dictionary.c.dict_code).order_by(dictionary.c.id)).scalars()) == ["sys_enable_status", "0", "1", "0"]
    engine.dispose()


def test_preflight_rejects_invalid_values_before_any_write():
    engine, user, notice, dictionary = database()
    with engine.begin() as connection:
        connection.execute(user.insert(), {"id": 1, "status": 0, "is_deleted": False})
        connection.execute(dictionary.insert(), {"id": 1, "status": 2})
        with pytest.raises(RuntimeError, match="Non-binary"):
            revision.flip_statuses(connection)
        assert connection.execute(select(user.c.status)).scalar_one() == 0
    engine.dispose()


def test_new_enum_node_defaults_and_notice_publication():
    from app.common.dict_values import BusinessStatus, EnableStatus, NoticeStatus
    from app.modules.system.dict.constants import DictType
    from app.modules.system.dict.registry import REGISTRY
    from app.modules.system.dict.schema import DictNodeWrite
    from app.modules.system.notice.schema import NoticeBatchStatusSchema

    assert EnableStatus.ENABLED.value == BusinessStatus.NORMAL.value == 1
    assert EnableStatus.DISABLED.value == BusinessStatus.DISABLED.value == 0
    assert DictNodeWrite(dict_name="Test", dict_code="test").status == 1
    from app.modules.system.dict.model import DictInfoModel
    assert str(DictInfoModel.__table__.c.status.server_default.arg) == "1"
    assert all(row["status"] == 1 for row in REGISTRY.nodes.values())
    assert [item.code for item in REGISTRY.definitions[DictType.SYS_NOTICE_STATUS].items] == [0, 1, 2]
    assert NoticeBatchStatusSchema(ids=[1], status=NoticeStatus.PUBLISHED).status == 1
    with pytest.raises(ValueError):
        NoticeBatchStatusSchema(ids=[1], status=2)


async def test_login_preparation_uses_new_enable_semantics(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.core.exceptions import CustomException
    from app.modules.system.auth.service import LoginService
    from app.modules.system.user.crud import UserCRUD

    enabled = SimpleNamespace(id=1, status=1)
    update = AsyncMock(return_value=enabled)
    monkeypatch.setattr(UserCRUD, "update_last_login", update)
    with pytest.raises(CustomException, match="停用"):
        await LoginService.prepare_user_for_login(None, SimpleNamespace(id=2, status=0))
    update.assert_not_awaited()
    assert await LoginService.prepare_user_for_login(None, enabled) is enabled
    update.assert_awaited_once_with(id=1)


def test_notice_publication_visibility_and_batch_contract(test_client, auth_headers):
    ids = {}
    for status in [0, 1, 2]:
        response = test_client.post(
            "/system/notice/create", headers=auth_headers, json={"notice_title": f"Publication migration test {status}", "notice_type": "1", "notice_content": "Test", "status": status}
        )
        assert response.status_code == 200, response.text
        ids[status] = response.json()["data"]["id"]
    visible = test_client.get("/system/notice/available", headers=auth_headers)
    assert visible.status_code == 200
    visible_ids = {row["id"] for row in visible.json()["data"]}
    assert ids[1] in visible_ids and ids[0] not in visible_ids and ids[2] not in visible_ids
    assert test_client.patch("/system/notice/status/batch", headers=auth_headers, json={"ids": [ids[0]], "status": 1}).status_code == 200
    visible_ids = {row["id"] for row in test_client.get("/system/notice/available", headers=auth_headers).json()["data"]}
    assert ids[0] in visible_ids
    assert test_client.patch("/system/notice/status/batch", headers=auth_headers, json={"ids": [ids[1]], "status": 0}).status_code == 200
    visible_ids = {row["id"] for row in test_client.get("/system/notice/available", headers=auth_headers).json()["data"]}
    assert ids[1] not in visible_ids
    assert test_client.patch("/system/notice/status/batch", headers=auth_headers, json={"ids": [ids[0]], "status": 2}).status_code == 422
