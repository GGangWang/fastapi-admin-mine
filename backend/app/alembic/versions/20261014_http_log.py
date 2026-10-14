"""HTTP log monthly schema v1 and management menu."""

from alembic import op

from app.common.http.storage import initial_months, months, prepare_locked

revision = "20261014_http_log"
down_revision = "20261014_enable_status"
branch_labels = None
depends_on = None


def upgrade():
    for month in initial_months():
        prepare_locked(op.get_bind(), month)
    from app.modules.system.http_log.menu import install_menu

    install_menu(op.get_bind())


def downgrade():
    from sqlalchemy import delete, select

    from app.common.http.storage import month_table

    bind = op.get_bind()
    from app.modules.system.menu.model import MenuModel
    from app.modules.system.role.model import RoleMenusModel

    menu = MenuModel.__table__
    ids = list(
        bind.execute(
            select(menu.c.id).where(
                menu.c.permission.in_(
                    [
                        "system:http_log:query",
                        "system:http_log:detail",
                        "system:http_log:body",
                        "system:http_log:download",
                    ]
                )
            )
        ).scalars()
    )
    if ids:
        relation = RoleMenusModel.__table__
        bind.execute(delete(relation).where(relation.c.menu_id.in_(ids)))
        bind.execute(delete(menu).where(menu.c.id.in_(ids)))
    for month in list(bind.execute(select(months.c.month)).scalars()):
        month_table(month).drop(bind, checkfirst=True)
    months.drop(bind, checkfirst=True)
