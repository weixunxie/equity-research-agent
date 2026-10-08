from backend.guard import RateLimiter, TTLCache


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_rate_limiter_blocks_after_limit_and_recovers():
    clock = Clock()
    limiter = RateLimiter(limit=2, window=60, clock=clock)
    for _ in range(2):
        assert limiter.retry_after("a") == 0
        limiter.hit("a")
    assert limiter.retry_after("a") == 60
    assert limiter.retry_after("b") == 0  # keys are independent

    clock.now += 45
    assert limiter.retry_after("a") == 15
    clock.now += 15
    assert limiter.retry_after("a") == 0


def test_rate_limiter_disabled_when_limit_is_zero():
    limiter = RateLimiter(limit=0, window=60)
    for _ in range(100):
        limiter.hit("a")
    assert limiter.retry_after("a") == 0


def test_cache_expires_and_evicts_least_recently_used():
    clock = Clock()
    cache = TTLCache(ttl=10, max_entries=2, clock=clock)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1  # touching "a" makes "b" the eviction candidate
    cache.set("c", 3)
    assert cache.get("b") is None
    assert cache.get("a") == 1 and cache.get("c") == 3

    clock.now += 10
    assert cache.get("a") is None


def test_cache_disabled_when_ttl_is_zero():
    cache = TTLCache(ttl=0)
    cache.set("a", 1)
    assert cache.get("a") is None
