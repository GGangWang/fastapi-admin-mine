"""Single-month queries; body columns are never selected by list/detail."""

import codecs

from sqlalchemy import LargeBinary, cast, func, select

from app.common.datetime_utils import parse_beijing
from app.common.http.storage import month_table, validate_month
from app.common.log_month import available_months
from app.common.log_time import http_timestamp
from app.core.exceptions import CustomException


class HttpLogService:
    def __init__(self, db):
        self.db = db

    async def available_months(self):
        return await available_months(self.db, "http")

    async def table(self, month):
        try:
            validate_month(month)
        except ValueError as exc:
            raise CustomException(msg=str(exc)) from exc
        if month not in await self.available_months():
            raise CustomException(msg="日志月份不存在")
        return month_table(month)

    @staticmethod
    def columns(table):
        return [column for column in table.c if column.name not in {"request_body", "response_body"}]

    async def page(self, month, page_no=1, page_size=20, **filters):
        table = await self.table(month)
        conditions = []
        for name, value in filters.items():
            if value is None or value == "":
                continue
            if name in {"start_time", "end_time"}:
                try:
                    parsed = parse_beijing(value).replace(tzinfo=None)
                except ValueError as exc:
                    raise CustomException(msg="时间格式无效") from exc
                if parsed.strftime("%Y%m") != month:
                    raise CustomException(msg="时间范围必须位于所选月份内")
                conditions.append(table.c.started_at >= parsed if name == "start_time" else table.c.started_at <= parsed)
            elif name in {"method", "result", "status_code", "id", "correlation_id"}:
                conditions.append(table.c[name] == value)
            elif name in {"service", "business", "operator", "url"}:
                conditions.append(table.c[name].contains(value, autoescape=True))
        if filters.get("start_time") and filters.get("end_time") and filters["start_time"] > filters["end_time"]:
            raise CustomException(msg="开始时间不能晚于结束时间")
        total = (await self.db.execute(select(func.count()).select_from(table).where(*conditions))).scalar_one()
        rows = (
            (await self.db.execute(select(*self.columns(table)).where(*conditions).order_by(table.c.started_at.desc(), table.c.id.desc()).offset((page_no - 1) * page_size).limit(page_size)))
            .mappings()
            .all()
        )
        return {"items": [self.output(row) for row in rows], "total": total, "page_no": page_no, "page_size": page_size, "has_next": page_no * page_size < total}

    @staticmethod
    def output(row):
        result = dict(row)
        if result.get("started_at") is not None:
            result["started_at"] = http_timestamp(result["started_at"])
        return result

    async def detail(self, month, log_id):
        table = await self.table(month)
        row = (await self.db.execute(select(*self.columns(table)).where(table.c.id == log_id))).mappings().first()
        if row is None:
            raise CustomException(msg="HTTP 日志不存在")
        return self.output(row)

    async def body(self, month, log_id, side, offset=0):
        table = await self.table(month)
        if side not in {"request", "response"}:
            raise CustomException(msg="正文方向无效")
        column = table.c[side + "_body"]
        dialect = self.db.bind.dialect.name
        binary = func.convert_to(column, "UTF8") if dialect == "postgresql" else cast(column, LargeBinary)
        # Fetch four extra bytes so the returned page ends at a UTF-8 boundary.
        row = (
            (
                await self.db.execute(
                    select(
                        func.substr(binary, offset + 1, 65540).label("chunk"),
                        func.octet_length(binary).label("size") if dialect != "sqlite" else func.length(binary).label("size"),
                        table.c[side + "_body_state"].label("state"),
                    ).where(table.c.id == log_id)
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise CustomException(msg="HTTP 日志不存在")
        raw = bytes(row["chunk"] or b"")[:65536]
        decoder = codecs.getincrementaldecoder("utf-8")()
        try:
            text = decoder.decode(raw, final=False)
        except UnicodeDecodeError as exc:
            raise CustomException(msg="正文偏移必须位于 UTF-8 字符边界") from exc
        pending = decoder.getstate()[0]
        consumed = len(raw) - len(pending)
        return {"text": text, "offset": offset, "next_offset": offset + consumed, "total_bytes": row["size"] or 0, "has_next": offset + consumed < (row["size"] or 0), "state": row["state"]}
