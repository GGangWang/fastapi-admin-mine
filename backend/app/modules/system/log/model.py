from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, MetaData, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.base_model import NAMING_CONVENTION
from app.utils.common_util import uuid4_str


def new_log_id() -> str:
    """Audit primary keys are 32 hexadecimal characters, without UUID separators."""
    return uuid4().hex


class LogBase(AsyncAttrs, DeclarativeBase):
    """Log templates are independent from application metadata and user relations."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class LogModelMixin(LogBase):
    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=new_log_id,
        comment="主键ID",
        index=True,
    )
    uuid: Mapped[str] = mapped_column(
        String(64),
        default=uuid4_str,
        nullable=False,
        unique=True,
        comment="UUID全局唯一标识",
        index=True,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否已删除(0:未删除 1:已删除)",
        index=True,
    )
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="创建时间",
        index=True,
    )
    updated_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        comment="更新时间",
    )
    deleted_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
        comment="删除时间",
    )


class LoginLogModel(LogModelMixin):
    """登录日志模型"""

    __tablename__: str = "sys_login_log"
    __table_args__: dict[str, str] = {"comment": "登录日志表"}

    status: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="登录状态(1成功 2失败)")
    description: Mapped[str | None] = mapped_column(Text, default=None, nullable=True, comment="备注")
    username: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="用户名")
    login_location: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="登录位置")
    login_ip: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="登录IP地址")
    request_os: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="操作系统")
    request_browser: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="浏览器")
    msg: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="提示消息")


class OperationLogModel(LogModelMixin):
    """操作日志模型"""

    __tablename__: str = "sys_operation_log"
    __table_args__: dict[str, str] = {"comment": "操作日志表"}

    username: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="操作人用户名")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="操作状态(0:成功 1:失败)")
    description: Mapped[str | None] = mapped_column(Text, default=None, nullable=True, comment="备注")
    request_path: Mapped[str] = mapped_column(String(255), index=True, comment="请求路径")
    request_method: Mapped[str] = mapped_column(String(10), comment="请求方式")
    request_payload: Mapped[str | None] = mapped_column(Text().with_variant(LONGTEXT(), "mysql"), comment="请求体")
    response_code: Mapped[int] = mapped_column(Integer, comment="响应状态码")
    response_json: Mapped[str | None] = mapped_column(Text().with_variant(LONGTEXT(), "mysql"), nullable=True, comment="响应体")
    process_time: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="处理时间")
    request_ip: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True, comment="请求IP")
