"""Read-only baseline and post-migration verification for the enable status switch."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.config.setting import settings

TABLES = (
    "sys_user",
    "sys_role",
    "sys_menu",
    "sys_dept",
    "sys_position",
    "sys_param",
    "sys_dict_info",
    "gen_table",
    "gen_table_column",
    "task_cornjob_node",
    "task_storage_node",
    "task_storage_workflow",
    "example_demo",
)
UNCHANGED = ("sys_notice", "sys_ticket", "sys_version", "sys_login_log", "sys_operation_log", "task_corn_job", "task_storage_transfer", "task_storage_transfer_step")


def capture(connection):
    existing = set(inspect(connection).get_table_names())
    result = {}
    for table in TABLES + UNCHANGED:
        if table not in existing:
            print(f"SKIP absent table: {table}")
            continue
        cols = {c["name"] for c in inspect(connection).get_columns(table)}
        if not {"id", "status"} <= cols:
            raise RuntimeError(f"Missing id/status: {table}")
        fields = "id, status" + (", is_deleted" if "is_deleted" in cols else "")
        rows = [dict(row) for row in connection.execute(text(f"SELECT {fields} FROM {table} ORDER BY id")).mappings()]
        if table in TABLES and any(row["status"] not in (0, 1) for row in rows):
            raise RuntimeError(f"Non-binary status in {table}")
        result[table] = rows
        counts = {str(value): sum(row["status"] == value for row in rows) for value in {row["status"] for row in rows}}
        print(f"{table}: {len(rows)} rows, status counts {counts}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["backup", "verify"])
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    engine = create_engine(settings.DB_URI, echo=False)
    with engine.connect() as connection:
        current = capture(connection)
        if args.mode == "backup":
            if args.path.exists():
                raise RuntimeError("Refusing to overwrite backup")
            args.path.parent.mkdir(parents=True, exist_ok=True)
            args.path.write_text(json.dumps({"created_at": datetime.now(UTC).isoformat(), "tables": current}, ensure_ascii=False, indent=2), encoding="utf-8")
            print("Status baseline saved")
        else:
            old = json.loads(args.path.read_text(encoding="utf-8"))["tables"]
            assert old.keys() == current.keys(), "Table set changed"
            for table, rows in old.items():
                expected = [dict(row, status=1 - row["status"]) if table in TABLES else row for row in rows]
                assert expected == current[table], f"Unexpected data change: {table}"
            print("All rows verified: enable semantics preserved; independent states and deletion flags unchanged")
    engine.dispose()
