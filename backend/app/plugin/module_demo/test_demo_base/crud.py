# -*- coding: utf-8 -*-

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema
from .model import TestDemoBaseModel
from .schema import TestDemoBaseCreateSchema, TestDemoBaseUpdateSchema


class TestDemoBaseCRUD(CRUDBase[TestDemoBaseModel, TestDemoBaseCreateSchema, TestDemoBaseUpdateSchema]):
    """基础测试管理数据层"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """
        初始化CRUD数据层

        参数:
        - auth (AuthSchema): 认证信息模型
        - db (AsyncSession): 数据库会话
        """
        super().__init__(model=TestDemoBaseModel, auth=auth, db=db)
