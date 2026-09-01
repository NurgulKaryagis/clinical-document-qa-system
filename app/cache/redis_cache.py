
from redis import Redis
from langchain_community.cache import RedisCache

from app.config import settings

def build_cache(client: Redis) -> RedisCache:
    return RedisCache(
        redis_=client,
        ttl= settings.redis_ttl_seconds
    )
    
def flush_cache(cache: RedisCache) -> None:
    return cache.clear()
    
    