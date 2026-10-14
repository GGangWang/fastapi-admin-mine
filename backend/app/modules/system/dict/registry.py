"""显式注册枚举字典；内部配置枚举不自动暴露。"""

import json
import re
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Any

from app.common.dict_values import BooleanValue, BusinessStatus, DictionarySource, EnableStatus
from app.common.enums import BusinessType

from .constants import DictType
from .frontend_dictionaries import register_frontend_dictionaries


def reservation(parent_id: int | None, code: str) -> str:
    return sha256(json.dumps([parent_id, code], ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class DictItem:
    code: str | int | bool
    label: str
    sort: int = 0
    status: int = EnableStatus.ENABLED.value
    is_default: bool = False
    css_class: str | None = None
    list_class: str | None = None
    description: str | None = None
    children: tuple["DictItem", ...] = ()
    children_enum: type[Enum] | None = None


@dataclass(frozen=True)
class EnumDictionary:
    code: str
    name: str
    items: tuple[DictItem, ...] = ()
    enum: type[Enum] | None = None


def enum_items(enum: type[Enum]) -> tuple[DictItem, ...]:
    items = tuple(item.value for item in enum.__members__.values())
    if not all(isinstance(item, DictItem) for item in items):
        raise ValueError("字典枚举成员必须使用 DictItem")
    return items


def code_string(value: Any) -> str:
    return str(value).lower() if isinstance(value, bool) else str(value)


class DictionaryRegistry:
    def __init__(self) -> None:
        self.definitions: dict[str, EnumDictionary] = {}
        self.nodes: dict[str, dict] = {}

    def register(self, definition: EnumDictionary) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", definition.code) or definition.code in self.definitions:
            raise ValueError("枚举字典编码无效或重复")
        if definition.items and definition.enum:
            raise ValueError("items 和 enum 只能指定一种")
        root_id = f"enum:{definition.code}"
        nodes = {
            root_id: {
                "id": root_id,
                "parent_id": None,
                "dict_level": 0,
                "dict_type": definition.code,
                "dict_code": definition.code,
                "dict_name": definition.name,
                "dict_sort": 0,
                "status": EnableStatus.ENABLED.value,
                "is_default": False,
                "source": "enum",
                "readonly": True,
            }
        }
        work = [(definition.items or (enum_items(definition.enum) if definition.enum else ()), root_id, (), frozenset({definition.enum}) if definition.enum else frozenset())]
        while work:
            items, parent, path, ancestors = work.pop()
            codes: set[str] = set()
            defaults = 0
            for item in items:
                code = code_string(item.code)
                if not code or code in codes or item.status not in (0, 1):
                    raise ValueError("枚举同级编码重复或状态无效")
                codes.add(code)
                defaults += int(item.is_default)
                if defaults > 1:
                    raise ValueError("同级枚举最多一个默认项")
                if id(item) in ancestors or (item.children_enum is not None and item.children_enum in ancestors):
                    raise ValueError("枚举子项存在循环引用")
                if item.children and item.children_enum:
                    raise ValueError("children 和 children_enum 只能指定一种")
                child_path = (*path, code)
                key = root_id + ":" + sha256(json.dumps(child_path, ensure_ascii=False).encode()).hexdigest()
                nodes[key] = {
                    "id": key,
                    "parent_id": parent,
                    "dict_level": len(child_path),
                    "dict_type": definition.code,
                    "dict_code": code,
                    "dict_name": item.label,
                    "dict_sort": item.sort,
                    "status": item.status,
                    "is_default": item.is_default,
                    "css_class": item.css_class,
                    "list_class": item.list_class,
                    "description": item.description,
                    "source": "enum",
                    "readonly": True,
                }
                children = item.children or (enum_items(item.children_enum) if item.children_enum else ())
                if children:
                    next_ancestors = ancestors | {id(item)}
                    if item.children_enum:
                        next_ancestors |= {item.children_enum}
                    work.append((children, key, child_path, next_ancestors))
        self.definitions[definition.code] = definition
        self.nodes.update(nodes)


REGISTRY = DictionaryRegistry()
REGISTRY.register(
    EnumDictionary(
        DictType.SYS_BUSINESS_STATUS,
        "系统业务状态",
        (DictItem(BusinessStatus.NORMAL.value, "正常", sort=0, list_class="success"), DictItem(BusinessStatus.DISABLED.value, "停用", sort=1, list_class="danger")),
    )
)
REGISTRY.register(
    EnumDictionary(DictType.SYS_TRUE_FALSE, "是否", (DictItem(BooleanValue.TRUE.value, "是", sort=0, list_class="success"), DictItem(BooleanValue.FALSE.value, "否", sort=1, list_class="danger")))
)
_LABELS = ("其他", "新增", "修改", "删除", "授权", "导出", "导入", "强退", "生成代码", "清空")
REGISTRY.register(EnumDictionary(DictType.SYS_BUSINESS_TYPE, "业务操作类型", tuple(DictItem(item.value, _LABELS[item.value], item.value) for item in BusinessType)))

REGISTRY.register(EnumDictionary(DictType.SYS_DICT_SOURCE, "字典来源", (DictItem(DictionarySource.DATABASE.value, "数据库", sort=0), DictItem(DictionarySource.ENUM.value, "枚举", sort=1))))


register_frontend_dictionaries(REGISTRY, EnumDictionary, DictItem)
