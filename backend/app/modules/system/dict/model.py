from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin


class DictInfoModel(ModelMixin):
    """根节点为类型，其余节点为字典项，不设固定业务层级。"""

    __tablename__ = "sys_dict_info"
    __table_args__ = (
        Index("ix_dict_info_type_parent", "dict_type", "parent_id", "is_deleted"),
        Index("ix_dict_info_parent_sort", "parent_id", "dict_sort"),
        {"comment": "统一树形字典"},
    )
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("sys_dict_info.id", ondelete="RESTRICT"), nullable=True)
    dict_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dict_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    dict_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dict_code: Mapped[str] = mapped_column(String(255), nullable=False)
    dict_sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    css_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    list_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NULL releases reservations after soft deletion on all supported dialects.
    active_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    default_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    legacy_type_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    legacy_data_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
