"""Invalidate only availability-dependent caches after a coordinated migration."""

import asyncio

from redis.asyncio import Redis

from app.common.enums import RedisInitKeyConfig
from app.config.setting import settings


async def clear():
    client = Redis.from_url(settings.REDIS_URI, decode_responses=True)
    names = ("SYSTEM_DICT", "SYSTEM_CONFIG", "USER_SESSION", "ACCESS_TOKEN", "REFRESH_TOKEN")
    total = 0
    try:
        for name in names:
            pattern = RedisInitKeyConfig[name].key + ":*"
            keys = [key async for key in client.scan_iter(match=pattern, count=100)]
            if keys:
                total += await client.delete(*keys)
            print(f"{name}: invalidated {len(keys)} keys")
    finally:
        await client.aclose()
    print(f"Invalidated {total} cache/session keys; users must sign in again")


if __name__ == "__main__":
    asyncio.run(clear())
