from contextlib import asynccontextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config.setting import settings
from app.core.base_model import MappedBase
from app.core.logger import logger


def missing_driver_error(db_url: str) -> RuntimeError:
    driver = make_url(db_url).get_driver_name()
    extra = {"psycopg": "kingbase", "asyncpg": "postgres", "aiosqlite": "sqlite", "aiomysql": "mysql", "pymysql": "mysql"}.get(driver)
    hint = f"uv sync --extra {extra}" if extra else "安装 URL 对应的数据库驱动"
    return RuntimeError(f"缺少数据库驱动 {driver}；请执行 {hint}")


def create_sync_engine(db_url: str = settings.DB_URI) -> Engine:
    """创建同步数据库引擎。

    同步引擎仅供同步组件使用：APScheduler SQLAlchemyJobStore、代码生成器 Inspector
    （后者经 asyncio.to_thread 在线程池中调用，见 gencode/crud.py 的 _sync_* 方法）。
    请求侧一律走异步会话，勿在事件循环内直接使用本引擎。

    参数:
    - db_url (str): 数据库连接URL,默认从配置中获取。

    返回:
    - Engine: 同步数据库引擎。
    """
    try:
        engine: Engine = create_engine(
            url=db_url,
            echo=settings.DATABASE_ECHO,
            pool_pre_ping=settings.POOL_PRE_PING,
            pool_recycle=settings.POOL_RECYCLE,
        )
    except ModuleNotFoundError:
        raise missing_driver_error(db_url) from None
    except Exception as error:
        logger.error("数据库引擎初始化失败: {}", type(error).__name__)
        raise
    return engine


def create_async_engine_and_session(db_url: str = settings.ASYNC_DB_URI, *, pool_options: dict | None = None) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """获取异步数据库会话连接。

    参数:
    - db_url (str): 异步数据库 URL，默认取配置项 ASYNC_DB_URI。

    返回:
    - tuple[AsyncEngine, async_sessionmaker[AsyncSession]]: 异步数据库引擎和会话工厂。
    """
    try:
        # 异步数据库引擎
        if make_url(db_url).get_backend_name() == "sqlite":
            async_engine = create_async_engine(
                url=db_url,
                echo=settings.DATABASE_ECHO,
                echo_pool=settings.ECHO_POOL,
                pool_pre_ping=settings.POOL_PRE_PING,
                pool_recycle=settings.POOL_RECYCLE,
                connect_args={"timeout": 30},  # 等待锁释放，避免并发写立即报 database is locked
            )

            @event.listens_for(async_engine.sync_engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
                """SQLite 启用 WAL + busy_timeout，提升读写并发（后台任务与请求并存时尤为必要）。"""
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.close()
        else:
            async_engine = create_async_engine(
                url=db_url,
                echo=settings.DATABASE_ECHO,
                echo_pool=settings.ECHO_POOL,
                pool_pre_ping=settings.POOL_PRE_PING,
                pool_recycle=settings.POOL_RECYCLE,
                **{
                    "pool_size": settings.POOL_SIZE,
                    "max_overflow": settings.MAX_OVERFLOW,
                    "pool_timeout": settings.POOL_TIMEOUT,
                    **(pool_options or {}),
                },
                pool_use_lifo=settings.POOL_USE_LIFO,
            )
    except ModuleNotFoundError:
        raise missing_driver_error(db_url) from None
    except Exception as error:
        logger.error("数据库引擎初始化失败: {}", type(error).__name__)
        raise
    else:
        # 异步数据库会话工厂
        AsyncSessionLocal = async_sessionmaker[AsyncSession](
            bind=async_engine,
            autocommit=settings.AUTOCOMMIT,
            autoflush=settings.AUTOFLUSH if settings.AUTOFETCH is None else settings.AUTOFETCH,
            expire_on_commit=settings.EXPIRE_ON_COMMIT,
            class_=AsyncSession,
        )
        return async_engine, AsyncSessionLocal


class DatabaseManager:
    """One engine/session factory per named source; sessions never change bindings."""

    def __init__(self):
        self._engines = {}
        self._factories = {}
        self._sync_engines = {}

    def _config(self, name):
        if name == "default":
            return None
        if name not in settings.DATASOURCES:
            raise ValueError(f"未配置的数据源: {name}")
        return settings.DATASOURCES[name]

    def url(self, name="default", *, synchronous=False):
        config = self._config(name)
        inherited = settings.DB_URI if synchronous else settings.ASYNC_DB_URI
        if config is None:
            return inherited
        explicit = config.sync_url if synchronous else config.async_url
        if explicit is not None:
            return explicit.get_secret_value()
        if config.database is None:
            raise ValueError(f"数据源 {name} 未配置同步连接")
        database = config.database
        if make_url(inherited).get_backend_name() == "sqlite" and not database.endswith(".db"):
            database += ".db"
        return make_url(inherited).set(database=database).render_as_string(hide_password=False)

    def engine(self, name="default"):
        config = self._config(name)
        if name not in self._engines:
            options = {} if config is None else {key: getattr(config, key) for key in ("pool_size", "max_overflow", "pool_timeout") if getattr(config, key) is not None}
            if name == "logs":
                default_url = make_url(self.url())
                log_url = make_url(self.url(name))
                if (default_url.host, default_url.port, default_url.database, default_url.get_backend_name()) == (log_url.host, log_url.port, log_url.database, log_url.get_backend_name()):
                    raise ValueError("logs 必须使用独立于 default 的数据库")
            engine, factory = create_async_engine_and_session(self.url(name), pool_options=options)
            self._engines[name], self._factories[name] = engine, factory
        return self._engines[name]

    def factory(self, name="default"):
        self.engine(name)
        return self._factories[name]

    def sync_engine(self, name="default"):
        self._config(name)
        if name not in self._sync_engines:
            self._sync_engines[name] = create_sync_engine(self.url(name, synchronous=True))
        return self._sync_engines[name]

    @asynccontextmanager
    async def session(self, name="default"):
        async with self.factory(name)() as session:
            async with session.begin():
                yield session
            for callback in session.info.pop("after_commit_callbacks", {}).values():
                await callback()

    async def dispose(self):
        try:
            for engine in self._engines.values():
                await engine.dispose()
        finally:
            for engine in self._sync_engines.values():
                engine.dispose()


databases = DatabaseManager()
engine = databases.sync_engine()
async_engine = databases.engine()
async_db_session = databases.factory()


async def create_tables() -> None:
    """创建数据库表（根据 ORM metadata）。

    返回:
    - None
    """
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(MappedBase.metadata.create_all)
    except Exception as e:
        logger.error(f"❌ 数据库表结构初始化失败: {e}")
        raise


async def drop_tables() -> None:
    """删除数据库表（根据 ORM metadata）。

    返回:
    - None
    """
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(MappedBase.metadata.drop_all)
    except Exception as e:
        logger.error(f"❌ 数据库表结构删除失败: {e}")
        raise
