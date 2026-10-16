"""Move the unchanged built-in retention task to the non-exec handler."""

from alembic import op
from sqlalchemy import inspect, update

from app.modules.task.cronjob.node.model import NodeModel

revision = "20261015_audit_log_cleanup"
down_revision = "20261015_audit_log_monthly"
branch_labels = None
depends_on = None

LEGACY_FUNC = (
    'def handler(**kwargs):\n    import asyncio\n    from app.modules.system.log.service import cleanup_expired_logs\n    return asyncio.run(cleanup_expired_logs(days=int(kwargs.get("days", 90))))'
)
BUILTIN_FUNC = "builtin:audit_log_cleanup"


def upgrade():
    bind = op.get_bind()
    if inspect(bind).has_table(NodeModel.__tablename__):
        table = NodeModel.__table__
        bind.execute(update(table).where(table.c.code == "log_cleanup", table.c.func == LEGACY_FUNC).values(func=BUILTIN_FUNC))


def downgrade():
    bind = op.get_bind()
    if inspect(bind).has_table(NodeModel.__tablename__):
        table = NodeModel.__table__
        bind.execute(update(table).where(table.c.code == "log_cleanup", table.c.func == BUILTIN_FUNC).values(func=LEGACY_FUNC))
