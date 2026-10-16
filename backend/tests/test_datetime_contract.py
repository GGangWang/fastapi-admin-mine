import asyncio
import io
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.common.datetime_utils import BEIJING, format_datetime, parse_beijing
from app.common.response import SuccessResponse, jsonable_response_content
from app.core.base_schema import AuthSchema, BaseQueryParam, BaseSchema
from app.core.exceptions import CustomException
from app.core.validator import DateTimeStr, datetime_validator
from app.modules.system.http_log.service import HttpLogService
from app.modules.system.log.schema import LoginLogQueryParam
from app.modules.system.log.service import LoginLogService
from app.modules.system.log.storage import month_model, prepare
from app.modules.task.cronjob.node.service import _build_job_trigger
from app.utils.common_util import search_to_dict
from app.utils.excel_util import ExcelUtil


@pytest.mark.parametrize("wall,utc", [
    ("2026-11-01 00:00:00", datetime(2026, 10, 31, 16, tzinfo=UTC)),
    ("2027-01-01 00:00:00", datetime(2026, 12, 31, 16, tzinfo=UTC)),
    ("2024-02-29 08:00:00", datetime(2024, 2, 29, tzinfo=UTC)),
])
def test_round_trip(wall, utc):
    assert datetime_validator(wall) == utc
    assert format_datetime(utc) == wall
    assert format_datetime(utc.replace(tzinfo=None)) == wall
    model = BaseSchema(created_time=utc)
    assert model.model_dump(mode="json")["created_time"] == wall
    assert jsonable_response_content(model)["created_time"] == wall
    assert jsonable_response_content({"nested": [{"time": utc}]})["nested"][0]["time"] == wall
    assert BaseSchema.model_validate(model.model_dump(mode="json")).created_time == utc


@pytest.mark.parametrize("value", ["2026-10-16T10:00:00Z", "2026-10-16T10:00:00+08:00", "2026-10-16 10:00:00+08:00", "2026-10-16 10:00:00.123", "2026-2-01 00:00:00", "2026-02-29 00:00:00", "2026-10-16", 1792101600, "1792101600"])
def test_strict_public_input(value):
    with pytest.raises(CustomException):
        BaseQueryParam(created_time=[value, "2026-10-17 00:00:00"])


def test_http_body_input_and_response():
    class Payload(BaseModel):
        when: DateTimeStr | None = None

    app = FastAPI()

    @app.exception_handler(CustomException)
    async def business_error(request, exc):
        return SuccessResponse(data=None, code=400, msg=exc.msg)

    @app.post("/echo")
    def echo(payload: Payload):
        if payload.when:
            assert payload.when.tzinfo == UTC
        return SuccessResponse(payload.model_dump())

    with TestClient(app) as client:
        assert client.post("/echo", json={"when": "2026-10-16 10:00:00"}).json()["data"]["when"] == "2026-10-16 10:00:00"
        assert client.post("/echo", json={"when": None}).json()["data"]["when"] is None
        assert client.post("/echo", json={"when": "2026-10-16T02:00:00Z"}).json()["code"] == 400


def test_sqlite_month_boundary_query_and_export(tmp_path):
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "time.db"))
        await prepare(engine, "login", "202611")
        model = month_model("login", "202611")
        async with async_sessionmaker(engine)() as db:
            db.add_all([
                model(id="a" * 32, username="midnight", created_time=datetime(2026, 10, 31, 16, tzinfo=UTC)),
                model(id="b" * 32, username="later", created_time=datetime(2026, 10, 31, 17, tzinfo=UTC)),
            ])
            await db.commit()
            query = LoginLogQueryParam(created_time=["2026-11-01 00:00:00", "2026-11-01 00:30:00"])
            assert search_to_dict(query)["created_time"][1][0] == datetime(2026, 10, 31, 16, tzinfo=UTC)
            page = await LoginLogService(AuthSchema(), db, "202611").page(1, 10, query)
            assert page.total == 1 and page.items[0].username == "midnight"
            raw = (await db.execute(select(model.created_time).where(model.id == "a" * 32))).scalar_one()
            assert raw == datetime(2026, 10, 31, 16)  # No historical data rewrite.
            data = ExcelUtil.export_list2excel([page.items[0].model_dump()], {"created_time": "时间"})
            wb = load_workbook(io.BytesIO(data))
            assert wb.active["A2"].value == "2026-11-01 00:00:00"
        await engine.dispose()
    asyncio.run(run())


def test_special_storage_and_schedule():
    from app.core.base_schema import SessionInfoSchema
    from app.modules.system.user.schema import UserOutSchema
    from app.modules.task.storage.core.base import StorageObject

    assert HttpLogService.output({"started_at": datetime(2026, 10, 16, 10)})["started_at"] == "2026-10-16 10:00:00"
    assert SessionInfoSchema(login_time=datetime(2026, 10, 16, 10)).model_dump(mode="json")["login_time"] == "2026-10-16 10:00:00"
    assert UserOutSchema(last_login=datetime(2026, 10, 16, 10)).model_dump(mode="json")["last_login"] == "2026-10-16 10:00:00"
    item = StorageObject(name="a", key="a", is_dir=False, modified_time=datetime(2026, 10, 16, 2, tzinfo=UTC))
    assert item.model_dump(mode="json")["modified_time"] == "2026-10-16 10:00:00"
    trigger = _build_job_trigger("date", "2027-01-01 00:00:00", None, None)
    assert trigger.run_date == datetime(2026, 12, 31, 16, tzinfo=UTC)
    assert trigger.run_date.utcoffset() == timedelta(hours=8)
    assert parse_beijing("2027-01-01 00:00:00").tzinfo == BEIJING
    with pytest.raises(ValueError):
        _build_job_trigger("interval", "0 1 0 0 0", "2026-10-16T02:00:00Z", None)


def test_legacy_example_wall_value_round_trip():
    from app.plugin.module_example.demo.schema import DemoCreateSchema, DemoOutSchema

    form = DemoCreateSchema(name="sample", datetime_val="2026-11-01 00:00:00")
    assert form.model_dump()["datetime_val"] == datetime(2026, 11, 1)
    output = DemoOutSchema.model_validate(form.model_dump())
    assert jsonable_response_content(output)["datetime_val"] == "2026-11-01 00:00:00"
    assert output.model_dump(mode="json")["datetime_val"] == "2026-11-01 00:00:00"
    for invalid in ("2026-10-31T16:00:00Z", "2026-11-01 00:00:00+08:00"):
        with pytest.raises(ValueError):
            DemoCreateSchema(name="sample", datetime_val=invalid)
