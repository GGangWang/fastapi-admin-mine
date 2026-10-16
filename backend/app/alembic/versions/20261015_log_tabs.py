"""Merge the HTTP log menu into log-management permissions."""

from alembic import op

from app.modules.system.http_log.menu import install_menu

revision = "20261015_log_tabs"
down_revision = "20261015_audit_log_cleanup"
branch_labels = None
depends_on = None


def upgrade():
    install_menu(op.get_bind())


def downgrade():
    raise RuntimeError("日志页签权限整合不能自动降级，请从备份恢复菜单及角色关系")
