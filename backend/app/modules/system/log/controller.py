from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, StreamResponse, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.dependencies import AuthPermission, get_current_user, log_db_getter
from app.core.router_class import OperationLogRoute
from app.utils.common_util import bytes2file_response

from .schema import (
    LoginLogDetailOutSchema,
    LoginLogOutSchema,
    LoginLogQueryParam,
    LogPaginationQueryParam,
    OperationLogDetailOutSchema,
    OperationLogOutSchema,
    OperationLogQueryParam,
)
from .service import LoginLogService, OperationLogService


def login_search_params(search: Annotated[LoginLogQueryParam, Query()]) -> LoginLogQueryParam:
    return search


def operation_search_params(search: Annotated[OperationLogQueryParam, Query()]) -> OperationLogQueryParam:
    return search


LogRouter = APIRouter(route_class=OperationLogRoute, prefix="/log", tags=["日志管理"])


@LogRouter.get("/login/detail/{id}", summary="获取登录日志详情", response_model=ResponseSchema[LoginLogDetailOutSchema])
async def get_log_detail_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_system:login_log:query"]))],
    db: Annotated[AsyncSession, Depends(log_db_getter)],
    month: Annotated[str, Query(description="日志月份 YYYYMM")],
    id: Annotated[str, Path(description="登录日志ID", min_length=32, max_length=32)],
) -> JSONResponse:
    result_dict: LoginLogDetailOutSchema = await LoginLogService(auth, db, month).detail(id=id)
    return SuccessResponse(data=result_dict, msg="获取登录日志详情成功")


@LogRouter.get("/login/list", summary="查询登录日志列表", response_model=ResponseSchema[PageResultSchema[LoginLogOutSchema]])
async def get_log_list_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_system:login_log:query"]))],
    db: Annotated[AsyncSession, Depends(log_db_getter)],
    month: Annotated[str, Query(description="日志月份 YYYYMM")],
    page: Annotated[LogPaginationQueryParam, Depends()],
    search: Annotated[LoginLogQueryParam, Depends(login_search_params)],
) -> JSONResponse:
    result_dict: PageResultSchema[LoginLogOutSchema] = await LoginLogService(auth, db, month).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result_dict, msg="查询登录日志列表成功")


@LogRouter.delete("/login/delete", summary="删除登录日志", response_model=ResponseSchema)
async def delete_log_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_system:login_log:delete"]))],
    db: Annotated[AsyncSession, Depends(log_db_getter)],
    month: Annotated[str, Query(description="日志月份 YYYYMM")],
    ids: Annotated[list[str], Body(description="ID列表")],
) -> JSONResponse:
    await LoginLogService(auth, db, month).delete(ids=ids)
    return SuccessResponse(msg="删除登录日志成功")


@LogRouter.get("/operation/detail/{id}", summary="获取操作日志详情", response_model=ResponseSchema[OperationLogDetailOutSchema], dependencies=[Security(AuthPermission(["module_system:log:query"]))])
async def get_operation_log_detail_controller(
    auth: Annotated[AuthSchema, Security(get_current_user)],
    db: Annotated[AsyncSession, Depends(log_db_getter)],
    month: Annotated[str, Query(description="日志月份 YYYYMM")],
    id: Annotated[str, Path(description="操作日志ID", min_length=32, max_length=32)],
) -> JSONResponse:
    result_dict: OperationLogDetailOutSchema = await OperationLogService(auth, db, month).detail(id=id)
    return SuccessResponse(data=result_dict, msg="获取操作日志详情成功")


@LogRouter.get(
    "/operation/list",
    summary="获取操作日志列表",
    response_model=ResponseSchema[PageResultSchema[OperationLogOutSchema]],
    dependencies=[Security(AuthPermission(["module_system:log:query"]))],
)
async def get_operation_log_list_controller(
    auth: Annotated[AuthSchema, Security(get_current_user)],
    db: Annotated[AsyncSession, Depends(log_db_getter)],
    month: Annotated[str, Query(description="日志月份 YYYYMM")],
    page: Annotated[LogPaginationQueryParam, Depends()],
    search: Annotated[OperationLogQueryParam, Depends(operation_search_params)],
) -> JSONResponse:
    result_dict: PageResultSchema[OperationLogOutSchema] = await OperationLogService(auth, db, month).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result_dict, msg="查询操作日志列表成功")


@LogRouter.delete("/operation/delete", summary="删除操作日志", response_model=ResponseSchema, dependencies=[Security(AuthPermission(["module_system:log:delete"]))])
async def delete_operation_log_controller(
    auth: Annotated[AuthSchema, Security(get_current_user)],
    db: Annotated[AsyncSession, Depends(log_db_getter)],
    month: Annotated[str, Query(description="日志月份 YYYYMM")],
    ids: Annotated[list[str], Body(description="ID列表")],
) -> JSONResponse:
    await OperationLogService(auth, db, month).delete(ids=ids)
    return SuccessResponse(msg="删除操作日志成功")


@LogRouter.post("/operation/export", summary="导出操作日志", dependencies=[Security(AuthPermission(["module_system:log:export"]))])
async def export_operation_log_list_controller(
    auth: Annotated[AuthSchema, Security(get_current_user)],
    db: Annotated[AsyncSession, Depends(log_db_getter)],
    month: Annotated[str, Query(description="日志月份 YYYYMM")],
    search: Annotated[OperationLogQueryParam, Body()],
) -> StreamingResponse:
    operation_log_query_result: list[OperationLogOutSchema] = await OperationLogService(auth, db, month).get_list(search=search)
    operation_log_export_result: bytes = await OperationLogService.export_list(operation_log_list=[item.model_dump() for item in operation_log_query_result])

    return StreamResponse(
        data=bytes2file_response(operation_log_export_result),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=operation_log.xlsx"},
    )


@LogRouter.get("/login/months", response_model=ResponseSchema[list[str]])
async def login_months(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_system:login_log:query"]))],
    db: Annotated[AsyncSession, Depends(log_db_getter)],
) -> JSONResponse:
    from .storage import available_months

    return SuccessResponse(data=await available_months(db, "login"))


@LogRouter.get("/operation/months", response_model=ResponseSchema[list[str]])
async def operation_months(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_system:log:query"]))],
    db: Annotated[AsyncSession, Depends(log_db_getter)],
) -> JSONResponse:
    from .storage import available_months

    return SuccessResponse(data=await available_months(db, "operation"))
