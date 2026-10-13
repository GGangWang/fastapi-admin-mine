# -*- coding: utf-8 -*-

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin, UserMixin


class TestDemoBaseModel(ModelMixin, UserMixin):
    """
    基础测试管理表
    """
    __tablename__: str = 'test_demo_base'
    __table_args__: dict[str, str] = {'comment': '基础测试管理'}
    user_name: Mapped[str | None] = mapped_column(String(64), nullable=True, comment='用户名')
    user_sex: Mapped[int | None] = mapped_column(Integer, nullable=True, comment='性别')

