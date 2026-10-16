"""Keep HTTP permissions under the shared log-management page."""

import json
from pathlib import Path

from sqlalchemy import insert, or_, select, update


def install_menu(connection):
    from app.modules.system.menu.model import MenuModel
    from app.modules.system.role.model import RoleMenusModel, RoleModel

    table = MenuModel.__table__
    relation = RoleMenusModel.__table__
    log_id = connection.execute(select(table.c.id).where(table.c.route_name == "Log", table.c.is_deleted.is_(False))).scalar()
    if log_id is None:
        return
    old_http = connection.execute(select(table.c.id).where(table.c.route_name == "HttpLog", table.c.is_deleted.is_(False))).scalar()
    old_permission = connection.execute(select(table.c.permission).where(table.c.id == log_id)).scalar()
    log_roles = list(connection.execute(select(relation.c.role_id).where(relation.c.menu_id == log_id)).scalars()) if old_permission == "module_system:log:query" else []

    def grant(role_id, menu_id):
        if connection.execute(select(relation.c.role_id).where(relation.c.role_id == role_id, relation.c.menu_id == menu_id)).first() is None:
            connection.execute(insert(relation).values(role_id=role_id, menu_id=menu_id))

    if old_http is not None:
        ids = list(connection.execute(select(table.c.id).where(or_(table.c.id == old_http, table.c.parent_id == old_http))).scalars())
        for role_id in connection.execute(select(relation.c.role_id).where(relation.c.menu_id.in_(ids))).scalars():
            grant(role_id, log_id)
        connection.execute(update(table).where(table.c.id == old_http).values(type=3, parent_id=log_id, route_name=None, route_path=None, component_path=None, hidden=False))
        connection.execute(update(table).where(table.c.parent_id == old_http).values(parent_id=log_id))
    connection.execute(update(table).where(table.c.id == log_id).values(permission=None))
    seed = json.loads((Path(__file__).resolve().parents[4] / "sql/sys_menu.json").read_text(encoding="utf-8"))
    node = next(child for item in seed if item.get("route_name") == "System" for child in item["children"] if child.get("route_name") == "Log")
    http_ids = []
    query_id = None
    for item in node["children"]:
        permission = item.get("permission", "")
        if permission != "module_system:log:query" and not permission.startswith("system:http_log:"):
            continue
        found = connection.execute(select(table.c.id).where(table.c.permission == permission, table.c.id != log_id, table.c.is_deleted.is_(False))).scalar()
        if found is None:
            values = {key: value for key, value in item.items() if key in table.c}
            found = connection.execute(insert(table).values(**values, parent_id=log_id)).inserted_primary_key[0]
        if permission == "module_system:log:query":
            query_id = found
        else:
            http_ids.append(found)
    if query_id:
        for role_id in log_roles:
            grant(role_id, query_id)
    roles = RoleModel.__table__
    for role_id in connection.execute(select(roles.c.id).where(roles.c.code == "SUPER_ADMIN")).scalars():
        for menu_id in [log_id, *http_ids]:
            grant(role_id, menu_id)
