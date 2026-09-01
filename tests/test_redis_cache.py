from unittest.mock import MagicMock

import pytest
from redis import Redis

from app.cache.redis_cache import build_cache, flush_cache
from app.config import settings


def make_fake_redis():
    return MagicMock(spec=Redis)


# --- build_cache ---

def test_build_cache_uses_configured_ttl():
    cache = build_cache(make_fake_redis())

    assert cache.ttl == settings.redis_ttl_seconds


def test_build_cache_rejects_non_redis_client():
    with pytest.raises(ValueError):
        build_cache(object())


# --- flush_cache ---

def test_flush_cache_triggers_flushdb():
    fake_redis = make_fake_redis()
    cache = build_cache(fake_redis)

    flush_cache(cache)

    fake_redis.flushdb.assert_called_once()


def test_flush_cache_does_not_touch_other_redis_methods():
    fake_redis = make_fake_redis()
    cache = build_cache(fake_redis)

    flush_cache(cache)

    fake_redis.set.assert_not_called()
    fake_redis.get.assert_not_called()
