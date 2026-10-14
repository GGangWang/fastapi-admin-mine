"""Idempotent menu installation for existing databases and fresh seeds."""

import json
from pathlib import Path

from sqlalchemy import insert, select


def install_menu(connection):
    from app.modules.system.menu.model import MenuModel
    from app.modules.system.role.model import RoleMenusModel, RoleModel

    table = MenuModel.__table__
    system_id = connection.execute(select(table.c.id).where(table.c.route_name == "System", table.c.is_deleted == False)).scalar()  # noqa: E712
    if system_id is None:
        return
    seed = json.loads((Path(__file__).resolve().parents[4] / "sql/sys_menu.json").read_text(encoding="utf-8"))
    node = next(child for item in seed if item.get("route_name") == "System" for child in item["children"] if child.get("route_name") == "HttpLog")
    ids = []

    def install(item, parent_id):
        values = {key: value for key, value in item.items() if key in table.c}
        found = connection.execute(select(table.c.id).where(table.c.permission == values["permission"], table.c.is_deleted == False)).scalar()  # noqa: E712
        if found is None:
            values["parent_id"] = parent_id
            found = connection.execute(insert(table).values(**values)).inserted_primary_key[0]
        ids.append(found)
        for child in item.get("children", []):
            install(child, found)

    install(node, system_id)
    role_ids = connection.execute(select(RoleModel.__table__.c.id).where(RoleModel.__table__.c.code == "SUPER_ADMIN")).scalars()
    relation = RoleMenusModel.__table__
    for role_id in role_ids:
        for menu_id in ids:
            if connection.execute(select(relation.c.role_id).where(relation.c.role_id == role_id, relation.c.menu_id == menu_id)).first() is None:
                connection.execute(insert(relation).values(role_id=role_id, menu_id=menu_id))
