import json
from datetime import UTC, datetime, timedelta

from redis.asyncio.client import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.datetime_utils import format_beijing_wall
from app.common.enums import RedisInitKeyConfig
from app.core.logger import logger
from app.core.redis_crud import RedisCURD
from app.core.security import decode_access_token
from app.modules.system.log.storage import TZ, login_relation
from app.modules.system.user.model import UserModel

from .schema import DashboardStatsSchema, LoginTrendItem, OnlineQueryParam, RecentLoginItem


class OnlineService:
    """在线用户管理模块服务层"""

    @staticmethod
    async def get_online_list(redis: Redis, search: OnlineQueryParam | None = None) -> list[dict]:
        keys = await RedisCURD(redis).scan_keys(f"{RedisInitKeyConfig.ACCESS_TOKEN.key}:*")
        tokens = await RedisCURD(redis).mget(keys)

        online_users = []
        for key, token in zip(keys, tokens, strict=True):
            if not token:
                continue
            try:
                payload = decode_access_token(token=token)
                session_id = payload.sub

                # 从 Redis 读取完整会话信息
                raw = await RedisCURD(redis).get(f"{RedisInitKeyConfig.USER_SESSION.key}:{session_id}")
                if not raw:
                    continue
                session_info = json.loads(raw)

                # 内联搜索匹配逻辑
                if search:
                    if search.name and search.name[1]:
                        kw = search.name[1].strip("%")
                        if kw.lower() not in session_info.get("name", "").lower():
                            continue
                    if search.ipaddr and search.ipaddr[1]:
                        kw = search.ipaddr[1].strip("%")
                        if kw not in session_info.get("ipaddr", ""):
                            continue
                    if search.login_location and search.login_location[1]:
                        kw = search.login_location[1].strip("%")
                        if kw.lower() not in session_info.get("login_location", "").lower():
                            continue

                # Internal cache may predate the public strict format (microseconds/offset).
                if session_info.get("login_time"):
                    cached_time = datetime.fromisoformat(session_info["login_time"])
                    session_info["login_time"] = format_beijing_wall(cached_time)
                online_users.append(session_info)
            except Exception:
                # token 已过期或无效，清理 Redis 中的脏数据
                key_str = key.decode() if isinstance(key, bytes) else key
                session_id = key_str.split(":")[-1]
                await RedisCURD(redis).delete(key_str)
                await RedisCURD(redis).delete(f"{RedisInitKeyConfig.REFRESH_TOKEN.key}:{session_id}")
                await RedisCURD(redis).delete(f"{RedisInitKeyConfig.USER_SESSION.key}:{session_id}")
                continue

        online_users.sort(key=lambda x: x.get("login_time", ""), reverse=True)
        return online_users

    @staticmethod
    async def get_current_user_sessions(redis: Redis, user_id: int) -> list[dict]:
        """获取当前用户的在线会话列表"""
        all_online = await OnlineService.get_online_list(redis)
        return [s for s in all_online if s.get("user_id") == user_id]

    @staticmethod
    async def delete_online(redis: Redis, session_id: str) -> None:
        await RedisCURD(redis).delete(f"{RedisInitKeyConfig.ACCESS_TOKEN.key}:{session_id}")
        await RedisCURD(redis).delete(f"{RedisInitKeyConfig.REFRESH_TOKEN.key}:{session_id}")
        await RedisCURD(redis).delete(f"{RedisInitKeyConfig.USER_SESSION.key}:{session_id}")
        logger.info(f"强制下线用户会话: {session_id}")

    @staticmethod
    async def clear_online(redis: Redis) -> None:
        await RedisCURD(redis).clear(f"{RedisInitKeyConfig.ACCESS_TOKEN.key}:*")
        await RedisCURD(redis).clear(f"{RedisInitKeyConfig.REFRESH_TOKEN.key}:*")
        await RedisCURD(redis).clear(f"{RedisInitKeyConfig.USER_SESSION.key}:*")
        logger.info("清除所有在线用户会话成功")

    @staticmethod
    async def get_dashboard_stats(db: AsyncSession, redis: Redis, log_db: AsyncSession) -> DashboardStatsSchema:
        """获取仪表盘统计数据"""
        local_today = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        today_start = local_today.astimezone(UTC)
        week_start = today_start - timedelta(days=6)
        end = today_start + timedelta(days=1)
        online_count = len(await OnlineService.get_online_list(redis))
        user_count = (await db.execute(select(func.count()).select_from(UserModel).where(UserModel.is_deleted.is_(False)))).scalar() or 0
        user_week_count = (
            await db.execute(
                select(func.count())
                .select_from(UserModel)
                .where(
                    UserModel.is_deleted.is_(False),
                    UserModel.created_time >= week_start,
                    UserModel.created_time < end,
                )
            )
        ).scalar() or 0
        today = await login_relation(log_db, today_start, end)
        counts = (
            await log_db.execute(
                select(func.count(), func.count(func.distinct(today.c.username)))
                .select_from(today)
                .where(
                    today.c.created_time >= today_start,
                    today.c.created_time < end,
                )
            )
        ).one()
        recent = await login_relation(log_db)
        recent_rows = (
            (
                await log_db.execute(
                    select(recent)
                    .where(recent.c.is_deleted.is_(False))
                    .order_by(
                        recent.c.created_time.desc(),
                        recent.c.id.desc(),
                        recent.c.uuid.desc(),
                    )
                    .limit(10)
                )
            )
            .mappings()
            .all()
        )
        recent_logins = [RecentLoginItem(username=r["username"], status=r["status"], login_time=r["created_time"], login_ip=r["login_ip"], login_location=r["login_location"]) for r in recent_rows]
        return DashboardStatsSchema(
            online_users=online_count,
            total_users=user_count,
            today_login_count=counts[0],
            today_unique_users=counts[1],
            week_user_created=user_week_count,
            login_trend=await OnlineService._build_login_trend(db, log_db, today_start=today_start, week_start=week_start),
            recent_logins=recent_logins,
        )

    @staticmethod
    async def _build_login_trend(db: AsyncSession, log_db: AsyncSession, *, today_start: datetime, week_start: datetime) -> list[LoginTrendItem]:
        """Seven Beijing calendar days including today; UTC bounds work on every dialect."""
        logs = await login_relation(log_db, week_start, today_start + timedelta(days=1))
        trend = []
        for offset in range(7):
            start = week_start + timedelta(days=offset)
            end = start + timedelta(days=1)
            row = (
                await log_db.execute(
                    select(func.count(), func.count(func.distinct(logs.c.username)))
                    .select_from(logs)
                    .where(
                        logs.c.is_deleted.is_(False),
                        logs.c.status == 1,
                        logs.c.created_time >= start,
                        logs.c.created_time < end,
                    )
                )
            ).one()
            new_users = (
                await db.execute(
                    select(func.count())
                    .select_from(UserModel)
                    .where(
                        UserModel.is_deleted.is_(False),
                        UserModel.created_time >= start,
                        UserModel.created_time < end,
                    )
                )
            ).scalar() or 0
            trend.append(LoginTrendItem(day=start.astimezone(TZ).date().isoformat(), logins=row[0], unique_users=row[1], new_users=new_users))
        return trend
