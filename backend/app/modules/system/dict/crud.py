from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import DictInfoModel
from .schema import DictNodeWrite


class DictInfoCRUD(CRUDBase[DictInfoModel, DictNodeWrite, DictNodeWrite]):
    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(DictInfoModel, auth, db)

    async def children(self, parent_id: int | None):
        child = aliased(DictInfoModel)
        has_children = select(child.id).where(child.parent_id == DictInfoModel.id, child.is_deleted.is_(False)).exists()
        query = select(DictInfoModel, has_children).where(DictInfoModel.is_deleted.is_(False), DictInfoModel.parent_id == parent_id).order_by(DictInfoModel.dict_sort, DictInfoModel.id)
        return list((await self.db.execute(query)).all())

    async def has_children(self, key: int) -> bool:
        query = select(select(DictInfoModel.id).where(DictInfoModel.parent_id == key, DictInfoModel.is_deleted.is_(False)).exists())
        return bool(await self.db.scalar(query))

    async def nodes(self, dict_type: str | None = None, lock: bool = False) -> list[DictInfoModel]:
        query = select(DictInfoModel).where(DictInfoModel.is_deleted.is_(False))
        if dict_type is not None:
            query = query.where(DictInfoModel.dict_type == dict_type)
        query = query.order_by(DictInfoModel.id) if lock else query.order_by(DictInfoModel.dict_sort, DictInfoModel.id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return list((await self.db.scalars(query)).all())

    async def lock_type(self, key: int) -> list[DictInfoModel]:
        node = await self.get_or_404(id=key)
        # Lock the type root first, including when edits target different leaves.
        # Re-read after waiting so concurrent renames cannot leave stale ORM state.
        for _ in range(2):
            root_query = (
                select(DictInfoModel)
                .where(DictInfoModel.dict_type == node.dict_type, DictInfoModel.parent_id.is_(None), DictInfoModel.is_deleted.is_(False))
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            root = (await self.db.scalars(root_query)).first()
            if root is not None:
                return await self.nodes(root.dict_type, lock=True)
            await self.db.refresh(node)
        from app.core.exceptions import CustomException

        raise CustomException(msg="所属字典类型不存在，请刷新后重试")
