import json
import re
from collections import defaultdict, deque
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.common.enums import RET
from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.database import async_db_session
from app.core.exceptions import CustomException

from .crud import DictInfoCRUD
from .model import DictInfoModel
from .registry import REGISTRY, reservation
from .schema import DictNodeOut, DictNodeQuery, DictNodeWrite


def node_key(value):
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.startswith("enum:"):
        return value
    try:
        result = int(value)
        if result > 0:
            return result
    except (ValueError, TypeError):
        pass
    raise CustomException(msg="字典节点标识无效")


def annotate(rows: list[dict]) -> list[dict]:
    parents = {row["parent_id"] for row in rows}
    return [dict(row, has_children=row["id"] in parents) for row in rows]


def active_nodes(rows: list[dict]) -> list[dict]:
    children = defaultdict(list)
    for row in rows:
        children[row["parent_id"]].append(row)
    result = []
    queue = deque(children[None])
    seen = set()
    while queue:
        node = queue.popleft()
        if node["id"] in seen:
            raise CustomException(msg="字典关系存在循环")
        seen.add(node["id"])
        if node["status"] == 0:
            result.append(node)
            queue.extend(children[node["id"]])
    return annotate(result)


def build_tree(rows: list[dict]) -> list[dict]:
    """Construct without recursive Python calls; roots themselves are omitted."""
    copies = {row["id"]: dict(row, children=[]) for row in rows}
    roots = {row["id"] for row in rows if row["parent_id"] is None}
    result = []
    for row in rows:
        node = copies[row["id"]]
        if row["parent_id"] in roots:
            result.append(node)
        elif row["parent_id"] in copies:
            copies[row["parent_id"]]["children"].append(node)
    return result


def iter_json(value):
    """Encode deeply nested trees without jsonable_encoder's recursive walk."""
    stack = [(False, value)]
    buffer, size = [], 0
    while stack:
        raw, current = stack.pop()
        if raw:
            token = current
        elif isinstance(current, dict):
            token = "{"
            stack.append((True, "}"))
            items = list(current.items())
            for index in range(len(items) - 1, -1, -1):
                key, item = items[index]
                if index < len(items) - 1:
                    stack.append((True, ","))
                stack.extend(((False, item), (True, ":"), (False, str(key))))
        elif isinstance(current, list):
            token = "["
            stack.append((True, "]"))
            for index in range(len(current) - 1, -1, -1):
                if index < len(current) - 1:
                    stack.append((True, ","))
                stack.append((False, current[index]))
        else:
            token = json.dumps(current, ensure_ascii=False, allow_nan=False)
        buffer.append(token)
        size += len(token)
        if size >= 16384:
            yield "".join(buffer)
            buffer, size = [], 0
    if buffer:
        yield "".join(buffer)


def export_rows(rows: list[dict]) -> list[list]:
    """One row per node; path depth never changes the Excel column count."""
    children = defaultdict(list)
    for row in rows:
        children[row["parent_id"]].append(row)
    queue = deque((row, ()) for row in children[None])
    result = []
    while queue:
        row, path = queue.popleft()
        path = (*path, row["dict_name"])
        result.append(
            [
                str(row["id"]),
                str(row["parent_id"] or ""),
                row["dict_type"],
                row["dict_level"],
                row["dict_name"],
                row["dict_code"],
                row["dict_sort"],
                row["status"],
                row["is_default"],
                row["source"],
                " / ".join(path),
            ]
        )
        queue.extend((child, path) for child in children[row["id"]])
    return result


class DictService:
    def __init__(self, auth, db):
        self.auth, self.db = auth, db
        self.crud = DictInfoCRUD(auth, db)

    def require(self, operation, level):
        if self.auth.user.is_superuser:
            return
        kind = "dict_type" if level == 0 else "dict_data"
        if f"module_system:{kind}:{operation}" not in self.auth.permissions:
            raise CustomException(msg="无权限操作", code=RET.FORBIDDEN.code)

    async def all_nodes(self, dict_type=None):
        rows = [DictNodeOut.model_validate(row).model_dump(mode="json") for row in await self.crud.nodes(dict_type)]
        rows.extend(dict(row) for row in REGISTRY.nodes.values() if dict_type is None or row["dict_type"] == dict_type)
        rows.sort(key=lambda row: (row["dict_sort"], row["dict_name"], str(row["id"])))
        return annotate(rows)

    async def detail(self, key):
        key = node_key(key)
        if isinstance(key, str):
            row = REGISTRY.nodes.get(key)
            if row is None:
                raise CustomException(msg="字典节点不存在")
            return dict(row, has_children=any(child["parent_id"] == key for child in REGISTRY.nodes.values()))
        row = await self.crud.get_or_404(id=key)
        result = DictNodeOut.model_validate(row).model_dump(mode="json")
        result["has_children"] = await self.crud.has_children(key)
        return result

    async def child_nodes(self, parent):
        rows = []
        if parent is None or isinstance(parent, int):
            rows = [dict(DictNodeOut.model_validate(row).model_dump(mode="json"), has_children=bool(has_children)) for row, has_children in await self.crud.children(parent)]
        if parent is None or isinstance(parent, str):
            enum_rows = [dict(row) for row in REGISTRY.nodes.values() if row["parent_id"] == parent]
            parents = {row["parent_id"] for row in REGISTRY.nodes.values()}
            rows.extend(dict(row, has_children=row["id"] in parents) for row in enum_rows)
        rows.sort(key=lambda row: (row["dict_sort"], row["dict_name"], str(row["id"])))
        return rows

    async def visible_children(self, key):
        path = await self.ancestors(key)
        if any(row["status"] != 0 for row in path):
            return []
        return [row for row in await self.child_nodes(node_key(key)) if row["status"] == 0]

    async def ancestors(self, key):
        node = await self.detail(key)
        result, seen = [], set()
        while node:
            if node["id"] in seen:
                raise CustomException(msg="字典关系存在循环")
            seen.add(node["id"])
            result.append(node)
            node = await self.detail(node["parent_id"]) if node["parent_id"] is not None else None
        return result[::-1]

    async def listing(self, search: DictNodeQuery, page_no=1, page_size=10, permission="query"):
        parent = node_key(search.parent_id)
        self.require(permission, 0 if parent is None else 1)
        if parent is not None:
            await self.detail(parent)
        rows = await self.child_nodes(parent)
        for field in ("source", "status", "dict_type"):
            value = getattr(search, field)
            if value is not None:
                rows = [row for row in rows if row[field] == value]
        for field in ("dict_name", "dict_code"):
            value = getattr(search, field)
            if value:
                rows = [row for row in rows if value.casefold() in row[field].casefold()]
        total = len(rows)
        start = (page_no - 1) * page_size
        return PageResultSchema[DictNodeOut](items=rows[start : start + page_size], total=total, page_no=page_no, page_size=page_size, has_next=start + page_size < total)

    def changed(self, redis, *types):
        pending = self.db.info.setdefault("after_commit_callbacks", {})
        for dict_type in set(types):

            async def invalidate(code=dict_type):
                # Generation keys prevent a reader of an old DB snapshot from
                # repopulating the new generation after a concurrent commit.
                await redis.set(f"system_dict:v2:generation:{code}", str(uuid4()))

            pending[f"dict:{dict_type}"] = invalidate

    async def _locked_nodes(self, key):
        if isinstance(node_key(key), str):
            raise CustomException(msg="枚举字典只读")
        node = await self.crud.get_or_404(id=node_key(key))
        # Lock the whole type in consistent order to serialize moves/defaults.
        rows = await self.crud.lock_type(node.id)
        return next(row for row in rows if row.id == node.id), rows

    async def save(self, redis, data: DictNodeWrite, key=None):
        self.require("create" if key is None else "update", 0 if data.parent_id is None else 1)
        existing, rows = (await self._locked_nodes(key)) if key is not None else (None, [])
        parent = None
        if data.parent_id is not None:
            if existing:
                destination = await self.crud.get_or_404(id=data.parent_id)
                if destination.dict_type != existing.dict_type:
                    raise CustomException(msg="不允许跨字典类型移动")
            parent, parent_rows = await self._locked_nodes(data.parent_id)
            if existing and parent.dict_type != existing.dict_type:
                raise CustomException(msg="不允许跨字典类型移动")
            rows = parent_rows
        if existing and ((existing.parent_id is None) != (parent is None)):
            raise CustomException(msg="不允许将根字典与普通字典项互相转换")
        if parent is None:
            if not re.fullmatch(r"[a-z][a-z0-9_]*", data.dict_code):
                raise CustomException(msg="字典类型须为小写字母开头的字母、数字或下划线")
            if data.dict_code in REGISTRY.definitions:
                raise CustomException(msg="该编码已被枚举字典保留")
            if data.is_default:
                raise CustomException(msg="根字典不能设置为默认项")
        by_id = {row.id: row for row in rows}
        cursor, visited = parent, set()
        while cursor:
            if (existing and cursor.id == existing.id) or cursor.id in visited:
                raise CustomException(msg="父节点不能是自身或后代")
            visited.add(cursor.id)
            cursor = by_id.get(cursor.parent_id)
        if any(row.id != (existing.id if existing else None) and row.parent_id == data.parent_id and row.dict_code == data.dict_code for row in rows):
            raise CustomException(msg="同级字典编码已存在")
        if data.is_default and any(row.id != (existing.id if existing else None) and row.parent_id == data.parent_id and row.is_default for row in rows):
            raise CustomException(msg="同级已有默认项")
        old_type = existing.dict_type if existing else None
        dict_type = parent.dict_type if parent else data.dict_code
        level = parent.dict_level + 1 if parent else 0
        obj = existing or DictInfoModel()
        for field, value in data.model_dump().items():
            setattr(obj, field, value)
        obj.dict_type, obj.dict_level = dict_type, level
        obj.active_key = reservation(data.parent_id, data.dict_code)
        obj.default_key = reservation(data.parent_id, "__default__") if data.is_default else None
        self.db.add(obj)
        if existing:
            # Propagate renamed types and changed levels across all descendants.
            descendants = defaultdict(list)
            for row in rows:
                descendants[row.parent_id].append(row)
            queue = deque(descendants[obj.id])
            while queue:
                child = queue.popleft()
                child.dict_type = dict_type
                child.dict_level = by_id[child.parent_id].dict_level + 1
                queue.extend(descendants[child.id])
        try:
            await self.db.flush()
        except IntegrityError as exc:
            raise CustomException(msg="同级编码或默认项冲突，请刷新后重试") from exc
        self.changed(redis, dict_type, *([old_type] if old_type else []))
        return await self.detail(obj.id)

    async def delete(self, redis, keys):
        # Check every node before mutation: a batch cannot partially succeed.
        targets = []
        for key in keys:
            node, rows = await self._locked_nodes(key)
            self.require("delete", node.dict_level)
            if any(row.parent_id == node.id for row in rows):
                raise CustomException(msg="存在下级字典，不能删除")
            targets.append(node)
        for node in targets:
            node.is_deleted, node.deleted_time = True, datetime.now(UTC)
            node.active_key = node.default_key = None
            self.changed(redis, node.dict_type)
        await self.db.flush()

    async def refresh(self, redis):
        self.require("update", 0)
        rows = await self.all_nodes()
        self.changed(redis, *(row["dict_type"] for row in rows if row["parent_id"] is None))

    async def effective(self, dict_type, redis=None):
        generation = await redis.get(f"system_dict:v2:generation:{dict_type}") if redis else None
        if isinstance(generation, bytes):
            generation = generation.decode()
        signature = sha256(json.dumps([row for row in REGISTRY.nodes.values() if row["dict_type"] == dict_type], sort_keys=True).encode()).hexdigest() if dict_type in REGISTRY.definitions else "db"
        key = f"system_dict:v2:{dict_type}:{signature}:{generation or '0'}"
        if redis:
            raw = await redis.get(key)
            if raw:
                try:
                    return json.loads(raw)
                except (ValueError, TypeError):
                    pass
        result = active_nodes(await self.all_nodes(dict_type))
        if redis:
            await redis.set(key, json.dumps(result, ensure_ascii=False), ex=3600)
        return result

    async def options(self, dict_type, redis=None):
        rows = await self.effective(dict_type, redis)
        root = next((row for row in rows if row["parent_id"] is None), None)
        if not root:
            return []
        return [dict(row, dict_label=row["dict_name"], dict_value=row["dict_code"], dict_type_id=root["id"]) for row in rows if row["parent_id"] == root["id"]]


class DictDataService:
    """Startup and public flat-query compatibility entrypoints."""

    @staticmethod
    async def init_cache(redis):
        async with async_db_session() as db:
            service = DictService(AuthSchema(), db)
            db_rows = await service.crud.nodes()
            conflicts = {row.dict_type for row in db_rows} & REGISTRY.definitions.keys()
            if conflicts:
                raise RuntimeError(f"数据库与枚举字典编码冲突: {', '.join(sorted(conflicts))}")
            types = {row.dict_type for row in db_rows} | REGISTRY.definitions.keys()
            for code in types:
                await redis.set(f"system_dict:v2:generation:{code}", str(uuid4()))
                await service.effective(code, redis)

    @staticmethod
    async def get_init_cache(redis, dict_type):
        async with async_db_session() as db:
            return await DictService(AuthSchema(), db).options(dict_type, redis)
