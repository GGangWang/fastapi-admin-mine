from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.common.dict_values import EnableStatus
from app.core.base_schema import BaseSchema


class DictNodeWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    parent_id: int | None = Field(default=None, gt=0)
    dict_name: str = Field(min_length=1, max_length=255)
    dict_code: str = Field(min_length=1, max_length=255)
    dict_sort: int = Field(default=0, ge=0)
    status: int = Field(default=EnableStatus.ENABLED.value, ge=0, le=1)
    is_default: bool = False
    css_class: str | None = Field(default=None, max_length=255)
    list_class: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class DictNodeOut(BaseSchema):
    id: int | str
    parent_id: int | str | None = None
    dict_level: int
    dict_type: str
    dict_name: str
    dict_code: str
    dict_sort: int = 0
    status: int = 0
    is_default: bool = False
    css_class: str | None = None
    list_class: str | None = None
    description: str | None = None
    source: Literal["database", "enum"] = "database"
    readonly: bool = False
    has_children: bool = False


class DictNodeQuery(BaseModel):
    parent_id: int | str | None = None
    dict_type: str | None = None
    dict_name: str | None = None
    dict_code: str | None = None
    source: Literal["database", "enum"] | None = None
    status: int | None = Field(default=None, ge=0, le=1)


class DictTypesQuery(BaseModel):
    mode: Literal["flat", "tree"] = "flat"
    dict_types: list[str] = Field(max_length=100)
