"""Explicit legacy two-table migration, also exercised against SQLite in tests."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import MetaData, Table, inspect, select

from .model import DictInfoModel
from .registry import REGISTRY, reservation


def migrate_legacy(connection):
    tables = set(inspect(connection).get_table_names())
    if "sys_dict_type" not in tables:
        DictInfoModel.__table__.create(connection, checkfirst=True)
        return
    metadata = MetaData()
    types_table = Table("sys_dict_type", metadata, autoload_with=connection)
    data_table = Table("sys_dict_data", metadata, autoload_with=connection) if "sys_dict_data" in tables else None
    types = list(connection.execute(select(types_table)).mappings())
    data = list(connection.execute(select(data_table)).mappings()) if data_table is not None else []
    by_id = {row["id"]: row for row in types}
    codes, values, defaults = set(), set(), set()
    for row in types:
        if row.get("is_deleted"):
            continue
        if row["dict_type"] in REGISTRY.definitions or row["dict_type"] in codes:
            raise RuntimeError(f"字典迁移失败：类型编码冲突 {row['dict_type']}")
        codes.add(row["dict_type"])
    for row in data:
        parent = by_id.get(row["dict_type_id"])
        if parent is None or parent["dict_type"] != row["dict_type"]:
            raise RuntimeError(f"字典迁移失败：无效类型关联 data:{row['id']}")
        if row.get("is_deleted"):
            continue
        if parent.get("is_deleted"):
            raise RuntimeError(f"字典迁移失败：有效字典项关联已删除类型 data:{row['id']}")
        key = (row["dict_type_id"], row["dict_value"])
        if key in values or (row.get("is_default") and row["dict_type_id"] in defaults):
            raise RuntimeError(f"字典迁移失败：同级编码或默认项冲突 data:{row['id']}")
        values.add(key)
        if row.get("is_default"):
            defaults.add(row["dict_type_id"])
    # Validate before DDL (MySQL DDL may commit automatically).
    DictInfoModel.__table__.create(connection, checkfirst=True)
    target = DictInfoModel.__table__
    existing = list(connection.execute(select(target)).mappings())
    if existing:
        mapped_types = {row["legacy_type_id"] for row in existing if row["legacy_type_id"] is not None}
        mapped_data = {row["legacy_data_id"] for row in existing if row["legacy_data_id"] is not None}
        if mapped_types == set(by_id) and mapped_data == {row["id"] for row in data}:
            return
        raise RuntimeError("字典迁移目标表已有非完整迁移数据，请人工检查，禁止覆盖")
    now = datetime.now(UTC)
    offset = max(by_id, default=0)

    def common(row):
        return {
            "uuid": row.get("uuid") or str(uuid4()),
            "created_time": row.get("created_time") or now,
            "updated_time": row.get("updated_time") or now,
            "deleted_time": row.get("deleted_time"),
            "is_deleted": bool(row.get("is_deleted", False)),
            "status": row["status"],
            "description": row.get("description"),
        }

    payload = []
    for row in types:
        payload.append(
            dict(
                common(row),
                id=row["id"],
                parent_id=None,
                dict_level=0,
                dict_type=row["dict_type"],
                dict_name=row["dict_name"],
                dict_code=row["dict_type"],
                dict_sort=0,
                is_default=False,
                css_class=None,
                list_class=None,
                active_key=None if row.get("is_deleted") else reservation(None, row["dict_type"]),
                default_key=None,
                legacy_type_id=row["id"],
                legacy_data_id=None,
            )
        )
    if payload:
        connection.execute(target.insert(), payload)
    payload = []
    for row in data:
        parent = row["dict_type_id"]
        payload.append(
            dict(
                common(row),
                id=offset + row["id"],
                parent_id=parent,
                dict_level=1,
                dict_type=row["dict_type"],
                dict_name=row["dict_label"],
                dict_code=row["dict_value"],
                dict_sort=row["dict_sort"],
                is_default=row["is_default"],
                css_class=row.get("css_class"),
                list_class=row.get("list_class"),
                active_key=None if row.get("is_deleted") else reservation(parent, row["dict_value"]),
                default_key=reservation(parent, "__default__") if row["is_default"] and not row.get("is_deleted") else None,
                legacy_type_id=None,
                legacy_data_id=row["id"],
            )
        )
    if payload:
        connection.execute(target.insert(), payload)
    # Explicit IDs require advancing PostgreSQL's SERIAL sequence.
    if connection.dialect.name == "postgresql":
        from sqlalchemy import text

        connection.execute(text("SELECT setval(pg_get_serial_sequence('sys_dict_info', 'id'), COALESCE((SELECT MAX(id) FROM sys_dict_info), 1), EXISTS(SELECT 1 FROM sys_dict_info))"))
