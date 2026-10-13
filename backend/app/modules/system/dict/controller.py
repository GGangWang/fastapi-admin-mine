import json
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Security
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import CreatedResponse, ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter, redis_getter
from app.core.router_class import OperationLogRoute

from .schema import DictNodeOut, DictNodeQuery, DictNodeWrite, DictTypesQuery
from .service import DictService, build_tree, export_rows, iter_json

DictRouter = APIRouter(route_class=OperationLogRoute, prefix="/dict", tags=["字典管理"])
DB = Annotated[AsyncSession, Depends(db_getter)]
Cache = Annotated[Redis, Depends(redis_getter)]
Read = Annotated[AuthSchema, Security(AuthPermission(["module_system:dict_type:query", "module_system:dict_data:query"]))]
Create = Annotated[AuthSchema, Security(AuthPermission(["module_system:dict_type:create", "module_system:dict_data:create"]))]
Edit = Annotated[AuthSchema, Security(AuthPermission(["module_system:dict_type:update", "module_system:dict_data:update"]))]
Delete = Annotated[AuthSchema, Security(AuthPermission(["module_system:dict_type:delete", "module_system:dict_data:delete"]))]
Export = Annotated[AuthSchema, Security(AuthPermission(["module_system:dict_type:export", "module_system:dict_data:export"]))]


@DictRouter.get("/nodes", response_model=ResponseSchema[PageResultSchema[DictNodeOut]])
async def nodes(auth: Read, db: DB, page: Annotated[PaginationQueryParam, Depends()], search: Annotated[DictNodeQuery, Query()]):
    return SuccessResponse(data=await DictService(auth, db).listing(search, page.page_no, page.page_size))


@DictRouter.get("/nodes/{key}", response_model=ResponseSchema[DictNodeOut])
async def detail(key: str, auth: Read, db: DB):
    service = DictService(auth, db)
    result = await service.detail(key)
    service.require("query", result["dict_level"])
    return SuccessResponse(data=result)


@DictRouter.get("/nodes/{key}/ancestors", response_model=ResponseSchema[list[DictNodeOut]])
async def ancestors(key: str, auth: Read, db: DB):
    service = DictService(auth, db)
    result = await service.ancestors(key)
    service.require("query", result[-1]["dict_level"])
    return SuccessResponse(data=result)


@DictRouter.post("/nodes", status_code=201, response_model=ResponseSchema[DictNodeOut])
async def create(data: DictNodeWrite, auth: Create, db: DB, redis: Cache):
    return CreatedResponse(data=await DictService(auth, db).save(redis, data))


@DictRouter.put("/nodes/{key}", response_model=ResponseSchema[DictNodeOut])
async def update(key: str, data: DictNodeWrite, auth: Edit, db: DB, redis: Cache):
    return SuccessResponse(data=await DictService(auth, db).save(redis, data, key))


@DictRouter.delete("/nodes", response_model=ResponseSchema[None])
async def delete(keys: Annotated[list[int | str], Body()], auth: Delete, db: DB, redis: Cache):
    await DictService(auth, db).delete(redis, keys)
    return SuccessResponse()


@DictRouter.get("/tree/{dict_type}", response_model=ResponseSchema[list[dict]])
async def tree(dict_type: str, db: DB, redis: Cache):
    envelope = json.loads(SuccessResponse().body)
    envelope["data"] = build_tree(await DictService(AuthSchema(), db).effective(dict_type, redis))
    return StreamingResponse(iter_json(envelope), media_type="application/json")


@DictRouter.get("/children/{key}", response_model=ResponseSchema[list[DictNodeOut]])
async def children(key: str, db: DB, redis: Cache):
    service = DictService(AuthSchema(), db)
    node = await service.detail(key)
    return SuccessResponse(data=[row for row in await service.effective(node["dict_type"], redis) if row["parent_id"] == node["id"]])


@DictRouter.post("/types", response_model=ResponseSchema[dict[str, list[dict]]])
async def types(data: DictTypesQuery, db: DB, redis: Cache):
    service = DictService(AuthSchema(), db)
    result = {code: (build_tree(await service.effective(code, redis)) if data.mode == "tree" else await service.options(code, redis)) for code in dict.fromkeys(data.dict_types)}
    if data.mode == "tree":
        envelope = json.loads(SuccessResponse().body)
        envelope["data"] = result
        return StreamingResponse(iter_json(envelope), media_type="application/json")
    return SuccessResponse(data=result)


@DictRouter.post("/cache/refresh", response_model=ResponseSchema[None])
async def refresh(auth: Edit, db: DB, redis: Cache):
    await DictService(auth, db).refresh(redis)
    return SuccessResponse()


@DictRouter.post("/export")
async def export(auth: Export, db: DB, search: DictNodeQuery, tree: bool = False):
    service = DictService(auth, db)
    service.require("export", 0 if tree or search.parent_id is None else 1)
    all_rows = await service.all_nodes(search.dict_type)
    if tree:
        roots = [
            row
            for row in all_rows
            if row["parent_id"] is None
            and (search.source is None or row["source"] == search.source)
            and (search.status is None or row["status"] == search.status)
            and (not search.dict_name or search.dict_name in row["dict_name"])
            and (not search.dict_code or search.dict_code in row["dict_code"])
        ]
        codes = {row["dict_type"] for row in roots}
        rows = [row for row in all_rows if row["dict_type"] in codes]
    else:
        page = await service.listing(search, 1, max(len(all_rows), 1), permission="export")
        ids = {row.id for row in page.items}
        # Keep ancestors while building paths, then select requested rows.
        rows = all_rows
    values = export_rows(rows)
    if not tree:
        values = [row for row in values if row[0] in {str(key) for key in ids}]
    book = Workbook(write_only=True)
    sheet = book.create_sheet("字典")
    sheet.append(["节点ID", "父节点ID", "字典类型", "层级", "名称", "编码", "排序", "状态", "默认", "来源", "路径"])
    for row in values:
        # Escape spreadsheet formula injection in administrator-entered values.
        sheet.append(["'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value for value in row])
    output = BytesIO()
    book.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="dictionary.xlsx"'})


# Existing business pages / generated pages retain the flat options contract.
@DictRouter.get("/data/info/{dict_type}", response_model=ResponseSchema[list[dict]])
async def flat_options(dict_type: str, db: DB, redis: Cache):
    return SuccessResponse(data=await DictService(AuthSchema(), db).options(dict_type, redis))


@DictRouter.get("/type/optionselect", response_model=ResponseSchema[list[DictNodeOut]])
async def type_options(auth: Read, db: DB):
    rows = [dict(row, dict_type=row["dict_code"]) for row in await DictService(auth, db).all_nodes() if row["parent_id"] is None and row["status"] == 0]
    return SuccessResponse(data=rows)


@DictRouter.get("/type/list", response_model=ResponseSchema[PageResultSchema[DictNodeOut]])
async def legacy_type_list(auth: Read, db: DB, page: Annotated[PaginationQueryParam, Depends()], dict_name: str | None = None, dict_type: str | None = None, status: int | None = None):
    return SuccessResponse(data=await DictService(auth, db).listing(DictNodeQuery(dict_name=dict_name, dict_type=dict_type, status=status), page.page_no, page.page_size))
