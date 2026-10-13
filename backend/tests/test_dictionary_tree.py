"""Dictionary invariants, legacy data migration, and enum integration."""

import asyncio
import json
from enum import Enum
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.modules.system.dict.migration import migrate_legacy
from app.modules.system.dict.model import DictInfoModel
from app.modules.system.dict.registry import REGISTRY, DictionaryRegistry, DictItem, EnumDictionary, reservation
from app.modules.system.dict.schema import DictNodeQuery, DictNodeWrite
from app.modules.system.dict.service import DictDataService, DictService, active_nodes, build_tree, export_rows, iter_json


def run_case(case):
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(DictInfoModel.__table__.create)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as db:
                auth = AuthSchema()
                auth.user.is_superuser = True
                await case(DictService(auth, db), db, AsyncMock())
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_deep_tree_move_rename_and_flat_compatibility():
    async def case(service, db, cache):
        root = await service.save(cache, DictNodeWrite(dict_name="分类", dict_code="test_deep"))
        parent = root
        for index in range(75):
            parent = await service.save(cache, DictNodeWrite(parent_id=parent["id"], dict_name=str(index), dict_code=str(index)))
        assert parent["dict_level"] == 75
        assert len(await service.ancestors(parent["id"])) == 76
        flat = await service.options("test_deep")
        assert len(flat) == 1 and flat[0]["dict_value"] == "0"
        rows = await service.all_nodes("test_deep")
        assert len(export_rows(rows)) == 76
        assert len(build_tree(active_nodes(rows))) == 1
        first = flat[0]
        with pytest.raises(CustomException):
            await service.save(cache, DictNodeWrite(parent_id=parent["id"], dict_name="循环", dict_code="0"), first["id"])
        await service.save(cache, DictNodeWrite(dict_name="新分类", dict_code="test_renamed"), root["id"])
        assert not await service.options("test_deep")
        assert len(await service.all_nodes("test_renamed")) == 76
        # Reparent a leaf within the same type; its level must be recalculated.
        moved = await service.save(cache, DictNodeWrite(parent_id=root["id"], dict_name="移动", dict_code="leaf"), parent["id"])
        assert moved["dict_level"] == 1

    run_case(case)


def test_defaults_duplicates_soft_delete_and_branch_status():
    async def case(service, db, cache):
        root = await service.save(cache, DictNodeWrite(dict_name="类型", dict_code="test_rules"))
        first = await service.save(cache, DictNodeWrite(parent_id=root["id"], dict_name="A", dict_code="a", is_default=True))
        for body in (DictNodeWrite(parent_id=root["id"], dict_name="B", dict_code="b", is_default=True), DictNodeWrite(parent_id=root["id"], dict_name="A2", dict_code="a")):
            with pytest.raises(CustomException):
                await service.save(cache, body)
        leaf = await service.save(cache, DictNodeWrite(parent_id=first["id"], dict_name="叶", dict_code="a"))
        with pytest.raises(CustomException):
            await service.delete(cache, [first["id"]])
        await service.save(cache, DictNodeWrite(parent_id=root["id"], dict_name="A", dict_code="a", status=1, is_default=True), first["id"])
        assert await service.options("test_rules") == []
        assert (await service.detail(leaf["id"]))["status"] == 0
        await service.save(cache, DictNodeWrite(parent_id=root["id"], dict_name="A", dict_code="a", status=0, is_default=True), first["id"])
        assert len(await service.effective("test_rules")) == 3
        await service.delete(cache, [leaf["id"]])
        await service.delete(cache, [first["id"]])
        await service.save(cache, DictNodeWrite(parent_id=root["id"], dict_name="替代", dict_code="a", is_default=True))
        # Cache operations are queued; no generation is published before commit.
        cache.set.assert_not_called()
        assert "dict:test_rules" in db.info["after_commit_callbacks"]

    run_case(case)


def test_cross_type_and_enum_writes_rejected():
    async def case(service, db, cache):
        first = await service.save(cache, DictNodeWrite(dict_name="A", dict_code="test_a"))
        other = await service.save(cache, DictNodeWrite(dict_name="B", dict_code="test_b"))
        child = await service.save(cache, DictNodeWrite(parent_id=first["id"], dict_name="项", dict_code="1"))
        with pytest.raises(CustomException):
            await service.save(cache, DictNodeWrite(parent_id=other["id"], dict_name="项", dict_code="1"), child["id"])
        with pytest.raises(CustomException):
            await service.save(cache, DictNodeWrite(dict_name="冒充枚举", dict_code="sys_true_false"))
        enum = "enum:sys_true_false"
        with pytest.raises(CustomException):
            await service.save(cache, DictNodeWrite(dict_name="修改", dict_code="x"), enum)
        with pytest.raises(CustomException):
            await service.delete(cache, [enum])
        result = await service.listing(DictNodeQuery(source="enum"), 1, 2)
        assert result.total == len(REGISTRY.definitions) and len(result.items) == 2 and result.has_next
        assert all(row.readonly for row in result.items)
        assert {row["dict_value"] for row in await service.options("sys_true_false")} == {"true", "false"}

    run_case(case)


def test_enum_nested_classes_and_conflicts():
    class Leaves(Enum):
        ONE = DictItem("01", "叶子")

    registry = DictionaryRegistry()
    registry.register(EnumDictionary("test_nested", "枚举树", (DictItem("a", "父", children_enum=Leaves), DictItem("b", "其他", children=(DictItem("01", "同值异路径"),)))))
    leaves = [row for row in registry.nodes.values() if row["dict_level"] == 2]
    assert len(leaves) == 2 and leaves[0]["id"] != leaves[1]["id"]
    assert all(row["dict_code"] == "01" for row in leaves)
    with pytest.raises(ValueError):
        registry.register(EnumDictionary("test_nested", "重复类型"))
    with pytest.raises(ValueError):
        registry.register(EnumDictionary("test_duplicate", "重复项", (DictItem(1, "A"), DictItem("1", "B"))))
    loop = DictItem("x", "循环")
    object.__setattr__(loop, "children", (loop,))
    with pytest.raises(ValueError):
        registry.register(EnumDictionary("test_loop", "循环", (loop,)))


def legacy_database():
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    types = Table(
        "sys_dict_type", metadata, Column("id", Integer, primary_key=True), Column("dict_type", String), Column("dict_name", String), Column("status", Integer), Column("is_deleted", Boolean)
    )
    data = Table(
        "sys_dict_data",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("dict_type_id", Integer),
        Column("dict_type", String),
        Column("dict_label", String),
        Column("dict_value", String),
        Column("dict_sort", Integer),
        Column("status", Integer),
        Column("is_default", Boolean),
        Column("is_deleted", Boolean),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(types.insert(), {"id": 1, "dict_type": "sys_user_sex", "dict_name": "用户性别", "status": 0, "is_deleted": False})
        connection.execute(
            data.insert(), {"id": 1, "dict_type_id": 1, "dict_type": "sys_user_sex", "dict_label": "男", "dict_value": "0", "dict_sort": 1, "status": 0, "is_default": True, "is_deleted": False}
        )
    return engine, types, data


def test_legacy_migration_preserves_codes_and_is_idempotent():
    engine, types, data = legacy_database()
    with engine.begin() as connection:
        migrate_legacy(connection)
        migrate_legacy(connection)
        result = list(connection.execute(select(DictInfoModel.__table__)).mappings())
        assert len(result) == 2
        assert result[0]["legacy_type_id"] == 1
        assert result[1]["legacy_data_id"] == 1 and result[1]["dict_code"] == "0"
        assert result[1]["parent_id"] == result[0]["id"]
        assert connection.execute(select(types)).first() is not None
        assert connection.execute(select(data)).first() is not None
    engine.dispose()


def test_migration_rejects_duplicate_defaults_before_copy():
    engine, types, data = legacy_database()
    with engine.begin() as connection:
        connection.execute(
            data.insert(), {"id": 2, "dict_type_id": 1, "dict_type": "sys_user_sex", "dict_label": "女", "dict_value": "1", "dict_sort": 2, "status": 0, "is_default": True, "is_deleted": False}
        )
        with pytest.raises(RuntimeError, match="默认项冲突"):
            migrate_legacy(connection)
    engine.dispose()


def test_unique_reservations_enforced_by_database():
    engine = create_engine("sqlite:///:memory:")
    DictInfoModel.__table__.create(engine)
    with engine.begin() as connection:
        values = {"dict_name": "A", "dict_type": "test_unique", "dict_code": "test_unique", "dict_level": 0, "active_key": reservation(None, "test_unique")}
        connection.execute(DictInfoModel.__table__.insert(), values)
        with pytest.raises(IntegrityError):
            connection.execute(DictInfoModel.__table__.insert(), values)
    engine.dispose()


def test_dictionary_http_integration(test_client, auth_headers):
    response = test_client.get("/system/dict/nodes", headers=auth_headers, params={"source": "enum"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["total"] == len(REGISTRY.definitions)
    response = test_client.get("/system/dict/data/info/sys_user_sex")
    assert response.status_code == 200 and response.json()["data"][0]["dict_label"] == "男"
    response = test_client.post("/system/dict/types", json={"dict_types": ["sys_user_sex", "sys_true_false"]})
    assert set(response.json()["data"]) == {"sys_user_sex", "sys_true_false"}
    response = test_client.post("/system/dict/export?tree=true", headers=auth_headers, json={})
    assert response.status_code == 200 and response.content.startswith(b"PK")
    # Verify write -> commit -> generation invalidation -> flat-query visibility.
    root_response = test_client.post("/system/dict/nodes", headers=auth_headers, json={"dict_name": "HTTP集成测试", "dict_code": "test_http_dictionary"})
    assert root_response.status_code == 201, root_response.text
    root = root_response.json()["data"]
    assert "root_id" not in root
    assert test_client.get("/system/dict/data/info/test_http_dictionary").json()["data"] == []
    child_response = test_client.post("/system/dict/nodes", headers=auth_headers, json={"parent_id": root["id"], "dict_name": "选项", "dict_code": "001"})
    assert child_response.status_code == 201, child_response.text
    child = child_response.json()["data"]
    assert test_client.get("/system/dict/data/info/test_http_dictionary").json()["data"][0]["dict_value"] == "001"
    tree = test_client.get("/system/dict/tree/test_http_dictionary")
    assert tree.status_code == 200 and tree.json()["data"][0]["dict_code"] == "001"
    readonly = test_client.put("/system/dict/nodes/enum:sys_true_false", headers=auth_headers, json={"dict_name": "禁止修改", "dict_code": "sys_true_false"})
    assert readonly.status_code == 400
    assert test_client.request("DELETE", "/system/dict/nodes", headers=auth_headers, json=[root["id"]]).status_code == 400
    # An invalid batch is atomic: the first leaf must remain when root validation fails.
    invalid = test_client.request("DELETE", "/system/dict/nodes", headers=auth_headers, json=[child["id"], root["id"]])
    assert invalid.status_code == 400
    assert test_client.get(f"/system/dict/nodes/{child['id']}", headers=auth_headers).status_code == 200
    assert test_client.request("DELETE", "/system/dict/nodes", headers=auth_headers, json=[child["id"]]).status_code == 200
    assert test_client.request("DELETE", "/system/dict/nodes", headers=auth_headers, json=[root["id"]]).status_code == 200


def test_tree_serialization_exceeds_python_recursion_depth():
    rows = [{"id": 0, "parent_id": None, "dict_name": "根"}]
    rows.extend({"id": index, "parent_id": index - 1, "dict_name": f"节点{index}"} for index in range(1, 1501))
    encoded = "".join(iter_json({"data": build_tree(rows)}))
    assert encoded.count('"children"') == 1500
    assert "节点1500" in encoded
    assert json.loads("".join(iter_json({"data": [1, {"a": "名称", "b": None}], "ok": True}))) == {"data": [1, {"a": "名称", "b": None}], "ok": True}


def test_type_permission_does_not_grant_item_writes():
    async def case(service, db, cache):
        root = await service.save(cache, DictNodeWrite(dict_name="权限", dict_code="test_permission"))
        service.auth.user.is_superuser = False
        service.auth.permissions = ["module_system:dict_type:create"]
        with pytest.raises(CustomException):
            await service.save(cache, DictNodeWrite(parent_id=root["id"], dict_name="越权", dict_code="bad"))

    run_case(case)


def test_startup_rejects_database_enum_collision():
    async def case(service, db, cache):
        db.add(DictInfoModel(dict_name="冲突", dict_code="sys_true_false", dict_type="sys_true_false",
                             dict_level=0, active_key=reservation(None, "sys_true_false")))
        await db.flush()
        with patch("app.modules.system.dict.service.async_db_session", return_value=db):
            with pytest.raises(RuntimeError, match="编码冲突"):
                await DictDataService.init_cache(cache)
    run_case(case)

def test_batch_flat_tree_and_source_dictionary(test_client):
    from app.modules.system.dict.constants import DictType
    flat = test_client.post('/system/dict/types', json={'dict_types': [DictType.SYS_DICT_SOURCE, DictType.SYS_TRUE_FALSE, DictType.SYS_DICT_SOURCE]})
    assert flat.status_code == 200
    data = flat.json()['data']
    assert set(data) == {DictType.SYS_DICT_SOURCE, DictType.SYS_TRUE_FALSE}
    assert [row['dict_value'] for row in data[DictType.SYS_DICT_SOURCE]] == ['database', 'enum']
    assert all(row['readonly'] for row in data[DictType.SYS_DICT_SOURCE])
    tree = test_client.post('/system/dict/types', json={'dict_types': [DictType.SYS_DICT_SOURCE], 'mode': 'tree'})
    assert tree.status_code == 200
    assert [row['dict_code'] for row in tree.json()['data'][DictType.SYS_DICT_SOURCE]] == ['database', 'enum']
    assert test_client.post('/system/dict/types', json={'dict_types': [], 'mode': 'invalid'}).status_code == 422


def test_registered_types_match_manifest():
    from pathlib import Path
    from app.modules.system.dict.constants import DictType
    from app.modules.system.dict.registry import REGISTRY
    entries = json.loads((Path(__file__).resolve().parents[2] / 'shared/dict-types.json').read_text(encoding='utf-8'))
    assert {item.value for item in DictType} == {entry['dict_type'] for entry in entries}
    assert set(REGISTRY.definitions) == {entry['dict_type'] for entry in entries if entry['source'] == 'enum'}
