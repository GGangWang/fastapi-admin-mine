"""Idempotent UUID primary-key upgrade for existing audit tables in the logs source."""

import re
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import MetaData, String, Table, inspect, select, update

from app.common.log_month import ddl_lock, months

from .model import new_log_id


def upgrade_connection(conn):
    converted = {}
    with ddl_lock(conn):
        names = inspect(conn).get_table_names()
        if months.name in names:
            versions = conn.execute(select(months.c.version).where(months.c.kind.in_(("login", "operation")))).scalars()
            if any(version not in (1, 2) for version in versions):
                raise RuntimeError("日志结构版本不支持此主键迁移")
        for name in names:
            if not re.fullmatch(r"sys_(login|operation)_log(?:_[0-9]{6})?", name):
                continue
            source = Table(name, MetaData(), autoload_with=conn)
            if isinstance(source.c.id.type, String) and source.c.id.type.length == 32:
                continue
            shadow_name = name + "_uuid32"
            backup_name = name + "_old_id"
            if shadow_name in names or backup_name in names:
                raise RuntimeError(f"主键迁移存在未处理的中间表: {name}，请先核对")
            if source.foreign_keys:
                raise RuntimeError(f"日志表仍有外键，拒绝自动迁移: {name}")
            target = source.to_metadata(MetaData(), name=shadow_name)
            target.c.id.type = String(32)
            target.c.id.autoincrement = False
            target.c.id.server_default = None
            from sqlalchemy import ColumnDefault

            target.c.id.default = ColumnDefault(new_log_id)
            for constraint in target.constraints:
                if constraint.name:
                    constraint.name = str(constraint.name).replace(name, shadow_name)
            for index in target.indexes:
                index.name = shadow_name + "_" + "_".join(c.name for c in index.columns)
            target.create(conn)
            expected = {}
            for row in conn.execute(select(source)).mappings():
                values = dict(row)
                try:
                    values["id"] = UUID(str(row.get("uuid"))).hex
                except (ValueError, TypeError, AttributeError):
                    values["id"] = uuid5(NAMESPACE_URL, str(row.get("uuid") or f"{name}:{row['id']}")).hex
                if values["id"] in expected:
                    raise RuntimeError(f"日志主键迁移发现重复 UUID: {name}")
                expected[values["id"]] = values
            if expected:
                conn.execute(target.insert(), list(expected.values()))
            actual = {row["id"]: dict(row) for row in conn.execute(select(target)).mappings()}
            if actual != expected:
                raise RuntimeError(f"日志主键迁移校验失败: {name}")
            quote = conn.dialect.identifier_preparer.quote
            if conn.dialect.name == "mysql":
                conn.exec_driver_sql(f"RENAME TABLE {quote(name)} TO {quote(backup_name)}, {quote(shadow_name)} TO {quote(name)}")
            else:
                conn.exec_driver_sql(f"ALTER TABLE {quote(name)} RENAME TO {quote(backup_name)}")
                conn.exec_driver_sql(f"ALTER TABLE {quote(shadow_name)} RENAME TO {quote(name)}")
            count = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {quote(name)}").scalar_one()
            if count != len(expected):
                raise RuntimeError(f"日志主键迁移行数不一致: {name}")
            conn.exec_driver_sql(f"DROP TABLE {quote(backup_name)}")
            converted[name] = count
        months.create(conn, checkfirst=True)
        conn.execute(update(months).where(months.c.kind.in_(("login", "operation"))).values(version=2))
    return converted


async def upgrade_ids(engine):
    async with engine.begin() as conn:
        return await conn.run_sync(upgrade_connection)
