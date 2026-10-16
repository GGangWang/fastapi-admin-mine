from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .storage import month_model, prepare, record_month


class MonthlyLogCRUD(CRUDBase):
    kind: str

    def __init__(self, auth: AuthSchema, db: AsyncSession, month: str) -> None:
        self.month = month
        super().__init__(model=month_model(self.kind, month), auth=auth, db=db)

    async def create(self, data):
        values = data.model_dump(exclude_none=True) if hasattr(data, "model_dump") else dict(data)
        occurred = values.setdefault("created_time", datetime.now(UTC))
        month = record_month(occurred)
        await prepare(self.db.bind, self.kind, month)
        self.model = month_model(self.kind, month)
        return await super().create(values)


class LoginLogCRUD(MonthlyLogCRUD):
    kind = "login"


class OperationLogCRUD(MonthlyLogCRUD):
    kind = "operation"
