import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class RecommendationCache:
    def __init__(self, redis: Redis, *, ttl_seconds: int) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def key(learner_id: str, version: int) -> str:
        return f"edu_dawnsynch:recommendations:{learner_id}:v{version}"

    async def get(self, learner_id: str, version: int) -> str | None:
        try:
            value = await self.redis.get(self.key(learner_id, version))
        except (RedisError, OSError):
            logger.warning("recommendation_cache_read_failed", extra={"learner_id": learner_id})
            return None
        if value is None:
            return None
        return value.decode() if isinstance(value, bytes) else str(value)

    async def set(self, learner_id: str, version: int, payload: str) -> None:
        try:
            await self.redis.set(
                self.key(learner_id, version), payload, ex=self.ttl_seconds
            )
        except (RedisError, OSError):
            logger.warning("recommendation_cache_write_failed", extra={"learner_id": learner_id})
