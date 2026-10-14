"""Switch only availability fields to 1=enabled, 0=disabled.

Revision ID: 20261014_enable_status
Revises: 20261013_dict_tree
"""

import hashlib
import json
import logging
import re

from alembic import op
from sqlalchemy import Integer, inspect, text

revision = "20261014_enable_status"
down_revision = "20261013_dict_tree"
branch_labels = None
depends_on = None
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
BINARY_DICT_TYPES = ("sys_enable_status", "sys_business_status", "sys_menu_status")


def preflight(connection):
    inspector = inspect(connection)
    existing = set(inspector.get_table_names())
    tables = []
    for table in TABLES:
        if table not in existing:
            logging.getLogger(__name__).info("Skip absent table %s", table)
            continue
        columns = {col["name"] for col in inspector.get_columns(table)}
        if not {"id", "status"} <= columns:
            raise RuntimeError(f"Missing id/status fields: {table}")
        invalid = connection.execute(text(f"SELECT COUNT(*) FROM {table} WHERE status IS NULL OR status NOT IN (0,1)")).scalar_one()
        if invalid:
            raise RuntimeError(f"Non-binary status values in {table}; no data was changed")
        tables.append(table)
    return tables


def flip_statuses(connection, tables=None):
    # Validate every table before the first write.
    tables = preflight(connection) if tables is None else tables
    for table in tables:
        connection.execute(text(f"UPDATE {table} SET status = CASE WHEN status=0 THEN 1 WHEN status=1 THEN 0 END"))
    if "sys_dict_info" in tables:
        placeholders = ",".join(f":t{i}" for i in range(len(BINARY_DICT_TYPES)))
        rows = list(
            connection.execute(
                text(f"SELECT id, parent_id, dict_code, is_deleted FROM sys_dict_info WHERE parent_id IS NOT NULL AND dict_type IN ({placeholders}) AND dict_code IN ('0','1')"),
                {f"t{i}": value for i, value in enumerate(BINARY_DICT_TYPES)},
            ).mappings()
        )
        # Release reservations before swapping sibling values, preserving defaults.
        for row in rows:
            connection.execute(text("UPDATE sys_dict_info SET active_key=NULL WHERE id=:id"), {"id": row["id"]})
        for row in rows:
            code = str(1 - int(row["dict_code"]))
            key = None if row["is_deleted"] else hashlib.sha256(json.dumps([row["parent_id"], code], ensure_ascii=False).encode()).hexdigest()
            connection.execute(text("UPDATE sys_dict_info SET dict_code=:code, active_key=:key WHERE id=:id"), {"code": code, "key": key, "id": row["id"]})


def migrate(default):
    connection = op.get_bind()
    tables = preflight(connection)
    # MySQL DDL commits implicitly: finish DDL before transactional data updates.
    for table in tables:
        if connection.dialect.name == "sqlite":
            with op.batch_alter_table(table) as batch:
                batch.alter_column("status", existing_type=Integer(), server_default=str(default))
        else:
            column = next(col for col in inspect(connection).get_columns(table) if col["name"] == "status")
            old_comment = column.get("comment") or "状态(0:启用 1:停用)"
            if default == 1:
                comment = re.sub(r"0:(启动|启用|正常) 1:(停用|禁用)", r"1:\1 0:\2", old_comment)
            else:
                comment = re.sub(r"1:(启动|启用|正常) 0:(停用|禁用)", r"0:\1 1:\2", old_comment)
            op.alter_column(table, "status", existing_type=Integer(), existing_nullable=False, server_default=str(default), comment=comment)
    flip_statuses(connection, tables)


def upgrade():
    migrate(1)


def downgrade():
    migrate(0)
