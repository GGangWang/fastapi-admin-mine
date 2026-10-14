from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Security
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import SuccessResponse
from app.core.database import async_db_session
from app.core.dependencies import AuthPermission, db_getter

from .service import HttpLogService

HttpLogRouter = APIRouter(prefix="/http-log", tags=["HTTP 调用日志"])


@HttpLogRouter.get("/file/{ticket}")
async def ticket_download(request: Request, ticket: str):
    import json

    from app.core.exceptions import CustomException

    value = await request.app.state.redis.getdel("http_log_download:" + ticket)
    if not value:
        raise CustomException(msg="下载凭据无效或已过期", code=403)
    month, log_id, side = json.loads(value)
    return body_download(month, log_id, side)


@HttpLogRouter.post("/{month}/{log_id}/ticket/{side}", dependencies=[Security(AuthPermission(["system:http_log:download"]))])
async def download_ticket(request: Request, db: Annotated[AsyncSession, Depends(db_getter)], month: str, log_id: str, side: Literal["request", "response"]):
    import json
    import secrets

    from app.core.exceptions import CustomException

    data = await HttpLogService(db).detail(month, log_id)
    if data[side + "_body_state"] != "recorded":
        raise CustomException(msg="正文未记录，无法下载")
    ticket = secrets.token_urlsafe(32)
    await request.app.state.redis.set("http_log_download:" + ticket, json.dumps([month, log_id, side]), ex=60)
    return SuccessResponse(data={"ticket": ticket})


@HttpLogRouter.get("/months", dependencies=[Security(AuthPermission(["system:http_log:query"]))])
async def available_months(db: Annotated[AsyncSession, Depends(db_getter)]):
    return SuccessResponse(data=await HttpLogService(db).available_months())


@HttpLogRouter.get("/list", dependencies=[Security(AuthPermission(["system:http_log:query"]))])
async def list_logs(
    db: Annotated[AsyncSession, Depends(db_getter)],
    month: str,
    page_no: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
    service: str | None = None,
    business: str | None = None,
    operator: str | None = None,
    method: str | None = None,
    url: str | None = None,
    status_code: int | None = None,
    result: str | None = None,
    id: str | None = None,
    correlation_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
):
    return SuccessResponse(
        data=await HttpLogService(db).page(
            month,
            page_no,
            page_size,
            service=service,
            business=business,
            operator=operator,
            method=method,
            url=url,
            result=result,
            id=id,
            correlation_id=correlation_id,
            start_time=start_time,
            end_time=end_time,
            **{"status_code": status_code},
        )
    )


@HttpLogRouter.get("/{month}/{log_id}", dependencies=[Security(AuthPermission(["system:http_log:detail"]))])
async def detail(db: Annotated[AsyncSession, Depends(db_getter)], month: str, log_id: str):
    return SuccessResponse(data=await HttpLogService(db).detail(month, log_id))


@HttpLogRouter.get("/{month}/{log_id}/body/{side}", dependencies=[Security(AuthPermission(["system:http_log:body"]))])
async def body(db: Annotated[AsyncSession, Depends(db_getter)], month: str, log_id: str, side: Literal["request", "response"], offset: Annotated[int, Query(ge=0)] = 0):
    return SuccessResponse(data=await HttpLogService(db).body(month, log_id, side, offset))


@HttpLogRouter.get("/{month}/{log_id}/download/{side}", dependencies=[Security(AuthPermission(["system:http_log:download"]))])
async def download(db: Annotated[AsyncSession, Depends(db_getter)], month: str, log_id: str, side: Literal["request", "response"]):
    from app.core.exceptions import CustomException

    row = await HttpLogService(db).detail(month, log_id)
    if row[side + "_body_state"] != "recorded":
        raise CustomException(msg="正文未记录，无法下载")
    return body_download(month, log_id, side)


def body_download(month, log_id, side):
    import re

    from app.core.exceptions import CustomException

    if not re.fullmatch(r"[0-9a-f]{32}", log_id):
        raise CustomException(msg="日志标识无效")

    async def chunks():
        offset = 0
        async with async_db_session() as session:
            service = HttpLogService(session)
            while True:
                page = await service.body(month, log_id, side, offset)
                yield page["text"].encode("utf-8")
                if not page["has_next"]:
                    break
                offset = page["next_offset"]

    return StreamingResponse(
        chunks(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="http-{month}-{log_id}-{side}.txt"',
            "X-Accel-Buffering": "no",
        },
    )
