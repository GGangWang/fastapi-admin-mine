"""Unify dictionary tables, retaining legacy tables for backup.

Revision ID: 20261013_dict_tree
Revises: None (first committed revision)
"""

from alembic import op

from app.modules.system.dict.migration import migrate_legacy

revision = "20261013_dict_tree"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    migrate_legacy(op.get_bind())


def downgrade():
    raise RuntimeError("新增多级数据无法无损写回旧两表结构；请恢复切换前备份和旧版本代码")
