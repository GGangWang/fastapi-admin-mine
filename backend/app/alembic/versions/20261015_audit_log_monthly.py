"""Audit monthly registry; legacy tables are retained as migration backups."""
from alembic import op
from app.modules.system.log.storage import months

revision = "20261015_audit_log_monthly"
down_revision = "20261014_http_log"
branch_labels = None
depends_on = None


def upgrade():
    months.create(op.get_bind(), checkfirst=True)


def downgrade():
    # Never discard populated audit tables on downgrade.
    from sqlalchemy import select
    if op.get_bind().execute(select(months.c.month).limit(1)).first():
        raise RuntimeError("月表含有审计数据，不能自动降级；请先备份并人工恢复旧表")
    months.drop(op.get_bind(), checkfirst=True)
