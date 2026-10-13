# -*- coding: utf-8 -*-

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from app.core.base_schema import BaseSchema, UserBySchema, BaseQueryParam, UserByQueryParam
from app.core.validator import DateTimeStr
class TestDemoBaseCreateSchema(BaseModel):
    """
    基础测试管理新增模型
    """
    user_name: str | None = Field(default=None, description='用户名')
    user_sex: int | None = Field(default=None, description='性别')


class TestDemoBaseUpdateSchema(BaseModel):
    """
    基础测试管理更新模型
    """
    user_name: str | None = Field(default=None, description='用户名')
    user_sex: int | None = Field(default=None, description='性别')


class TestDemoBaseOutSchema(TestDemoBaseCreateSchema, BaseSchema, UserBySchema):
    """
    基础测试管理响应模型
    """
    model_config = ConfigDict(from_attributes=True)


class TestDemoBaseQueryParam(BaseQueryParam, UserByQueryParam):
    """基础测试管理查询参数"""

    user_name: str | None = Field(None, description="用户名", json_schema_extra={"q": "like"})
    user_sex: int | None = Field(None, description="性别", json_schema_extra={"q": "eq"})
