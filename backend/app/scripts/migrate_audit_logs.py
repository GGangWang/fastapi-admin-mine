"""Offline, resumable audit log migration. Stop application writers before invoking."""

from collections import Counter
from datetime import datetime

from sqlalchemy import func, insert, inspect, or_, select, text

from app.modules.system.log.storage import SOURCES, month_bounds, month_model, prepare, record_month, utc_time


def equivalent(left, right):
    for key, value in left.items():
        other = right[key]
        if isinstance(value, datetime) and isinstance(other, datetime):
            if utc_time(value) != utc_time(other):
                return False
        elif value != other:
            return False
    return True


async def migrate(engine, batch_size=1000):
    if batch_size < 1:
        raise ValueError("batch_size 必须大于 0")
    report = {}
    for kind, model in SOURCES.items():
        source = model.__table__
        async with engine.connect() as conn:
            exists = await conn.run_sync(lambda c, source=source: inspect(c).has_table(source.name))
        if not exists:
            report[kind] = {"inserted": 0, "verified": 0, "months": {}}
            continue
        last_id = None
        inserted = verified = 0
        counts = Counter()
        while True:
            async with engine.connect() as conn:
                statement = select(source).order_by(source.c.id).limit(batch_size)
                if last_id is not None:
                    statement = statement.where(source.c.id > last_id)
                rows = (await conn.execute(statement)).mappings().all()
            if not rows:
                break
            for month in {record_month(row["created_time"]) for row in rows}:
                await prepare(engine, kind, month)
            async with engine.begin() as conn:
                for row in rows:
                    month = record_month(row["created_time"])
                    table = month_model(kind, month).__table__
                    matches = (await conn.execute(select(table).where(or_(table.c.id == row["id"], table.c.uuid == row["uuid"])))).mappings().all()
                    if matches:
                        if len(matches) != 1 or not equivalent(row, matches[0]):
                            raise RuntimeError(f"迁移冲突 {table.name} id={row['id']} uuid={row['uuid']}，未覆盖")
                    else:
                        await conn.execute(insert(table).values(**dict(row)))
                        inserted += 1
                    actual = (await conn.execute(select(table).where(table.c.uuid == row["uuid"]))).mappings().one()
                    if not equivalent(row, actual):
                        raise RuntimeError(f"迁移校验失败 {table.name} id={row['id']}")
                    verified += 1
                    counts[month] += 1
            last_id = rows[-1]["id"]
        # Explicit IDs advance SQLite/MySQL counters. PostgreSQL sequences need repair.
        async with engine.begin() as conn:
            for month, expected in counts.items():
                table = month_model(kind, month).__table__
                start, end = month_bounds(month)
                original_count = (await conn.execute(select(func.count()).select_from(source).where(source.c.created_time >= start, source.c.created_time < end))).scalar_one()
                actual_count = (await conn.execute(select(func.count()).select_from(table))).scalar_one()
                if original_count != expected or actual_count != expected:
                    raise RuntimeError(f"月表记录数不一致 {table.name}: source={original_count}, target={actual_count}, verified={expected}")
                if conn.dialect.name == "postgresql" and not isinstance(table.c.id.type, __import__("sqlalchemy").String):
                    await conn.execute(
                        text("SELECT setval(pg_get_serial_sequence(:table, 'id'), COALESCE((SELECT MAX(id) FROM " + table.name + "), 1), EXISTS(SELECT 1 FROM " + table.name + "))"),
                        {"table": table.name},
                    )
        report[kind] = {"inserted": inserted, "verified": verified, "months": dict(counts)}
    return report
