from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.datetime_utils import datetime_input
from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.core.logger import logger
from app.utils.common_util import search_to_dict
from app.utils.excel_util import ExcelUtil

from .crud import LoginLogCRUD, OperationLogCRUD
from .schema import (
    LoginLogDetailOutSchema,
    LoginLogOutSchema,
    LoginLogQueryParam,
    OperationLogDetailOutSchema,
    OperationLogOutSchema,
    OperationLogQueryParam,
)
from .storage import available_months, checked_month, month_bounds


class MonthlyLogService:
    kind: str

    async def exists(self) -> bool:
        return self.month in await available_months(self.db, self.kind)

    def validate_search(self, search):
        if search is None:
            return
        start, end = month_bounds(self.month)
        for field in ("created_time", "updated_time"):
            values = getattr(search, field, None)
            if not values:
                continue
            if len(values) != 2:
                raise CustomException(msg="时间范围必须包含开始和结束时间")
            parsed = [datetime_input(v) for v in values]
            if parsed[0] > parsed[1] or any(not start <= value < end for value in parsed):
                raise CustomException(msg="时间范围必须位于所选月份内，且开始时间不能晚于结束时间")

    async def require_month(self):
        if not await self.exists():
            raise CustomException(msg="该数据不存在")


class LoginLogService(MonthlyLogService):
    kind = "login"
    """登录日志管理服务"""

    def __init__(self, auth: AuthSchema, db: AsyncSession, month: str) -> None:
        self.auth = auth
        self.db = db
        self.month = checked_month(month)

    async def detail(self, id: str) -> LoginLogDetailOutSchema:
        await self.require_month()
        obj = await LoginLogCRUD(self.auth, self.db, self.month).get_or_404(id=id)
        return LoginLogDetailOutSchema.model_validate(obj)

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: LoginLogQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[LoginLogOutSchema]:
        self.validate_search(search)
        if not await self.exists():
            return PageResultSchema(page_no=page_no, page_size=page_size, total=0, has_next=False, items=[])
        return await LoginLogCRUD(self.auth, self.db, self.month).page(
            offset=(page_no - 1) * page_size,
            limit=page_size,
            order_by=order_by or [{"created_time": "desc"}, {"id": "desc"}],
            search=search_to_dict(search),
            out_schema=LoginLogOutSchema,
        )

    async def delete(self, ids: list[str]) -> None:
        if not ids:
            raise CustomException(msg="删除失败，删除对象不能为空")

        await self.require_month()
        existing = await LoginLogCRUD(self.auth, self.db, self.month).get_list(search={"id": ("in", ids)})
        existing_map = {obj.id for obj in existing}
        for nid in ids:
            if nid not in existing_map:
                raise CustomException(msg=f"删除失败，ID为{nid}的数据不存在")

        await LoginLogCRUD(self.auth, self.db, self.month).delete(ids=ids)


class OperationLogService(MonthlyLogService):
    kind = "operation"
    """操作日志管理服务"""

    def __init__(self, auth: AuthSchema, db: AsyncSession, month: str) -> None:
        self.auth = auth
        self.db = db
        self.month = checked_month(month)

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: OperationLogQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[OperationLogOutSchema]:
        self.validate_search(search)
        if not await self.exists():
            return PageResultSchema(page_no=page_no, page_size=page_size, total=0, has_next=False, items=[])
        crud = OperationLogCRUD(self.auth, self.db, self.month)
        return await crud.page(
            offset=(page_no - 1) * page_size,
            limit=page_size,
            order_by=order_by or [{"created_time": "desc"}, {"id": "desc"}],
            search=search_to_dict(search),
            out_schema=OperationLogOutSchema,
        )

    async def detail(self, id: str) -> OperationLogDetailOutSchema:
        await self.require_month()
        crud = OperationLogCRUD(self.auth, self.db, self.month)
        obj = await crud.get_or_404(id=id)
        return OperationLogDetailOutSchema.model_validate(obj)

    async def delete(self, ids: list[str]) -> None:
        if not ids:
            raise CustomException(msg="删除失败，删除对象不能为空")
        await self.require_month()
        existing = await OperationLogCRUD(self.auth, self.db, self.month).get_list(search={"id": ("in", ids)})
        existing_map = {obj.id for obj in existing}
        for nid in ids:
            if nid not in existing_map:
                raise CustomException(msg="删除失败，该数据不存在")
        crud = OperationLogCRUD(self.auth, self.db, self.month)
        await crud.delete(ids=ids)

    async def get_list(
        self,
        search: OperationLogQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> list[OperationLogOutSchema]:
        self.validate_search(search)
        if not await self.exists():
            return []
        crud = OperationLogCRUD(self.auth, self.db, self.month)
        obj_list = await crud.get_list(
            search=search_to_dict(search),
            order_by=order_by or [{"created_time": "desc"}, {"id": "desc"}],
        )
        return [OperationLogOutSchema.model_validate(obj) for obj in obj_list]

    @staticmethod
    async def export_list(operation_log_list: list[dict[str, Any]]) -> bytes:
        """导出操作日志列表"""
        mapping_dict = {
            "id": "日志编号",
            "request_path": "请求路径",
            "request_method": "请求方法",
            "request_ip": "请求IP",
            "request_payload": "请求参数",
            "response_code": "响应状态码",
            "process_time": "耗时(ms)",
            "created_time": "操作时间",
            "created_id": "操作用户ID",
        }
        return await ExcelUtil.aexport_list2excel(list_data=operation_log_list, mapping_dict=mapping_dict)


async def cleanup_expired_logs(days: int = 90) -> dict:
    """Physical retention across audit month tables, preserving the scheduler contract."""
    from app.core.database import databases

    from .storage import cleanup

    stats = await cleanup(databases.engine("logs"), days)
    logger.info("日志保留清理完成: {}", stats)
    return stats
