import redis.asyncio as aioredis
import structlog
from app.config import settings

log = structlog.get_logger()

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _redis


async def check_redis_health() -> bool:
    try:
        r = await get_redis()
        return await r.ping()
    except Exception as e:
        log.warning("redis.health.failed", error=str(e))
        return False


async def close_redis():
    global _redis
    if _redis:
        try:
            await _redis.aclose()
        except Exception:
            pass
        _redis = None
