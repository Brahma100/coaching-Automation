import sys
import time
import unittest

from app.cache import CacheManager, MemoryCacheBackend, RedisCacheBackend, cache, cache_key, cached_view


class CacheTests(unittest.TestCase):
    def setUp(self):
        cache.invalidate_prefix('today_view')
        cache.invalidate_prefix('inbox')
        cache.invalidate('admin_ops')
        cache.invalidate_prefix('student_dashboard')

    def test_cache_hit_miss(self):
        key = cache_key('today_view', 'teacher:1')
        self.assertIsNone(cache.get_cached(key))
        cache.set_cached(key, {'ok': True}, ttl=5)
        self.assertEqual(cache.get_cached(key), {'ok': True})

    def test_cache_invalidate_prefix(self):
        cache.set_cached(cache_key('today_view', 'teacher:1'), {'a': 1}, ttl=5)
        cache.set_cached(cache_key('today_view', 'teacher:2'), {'b': 2}, ttl=5)
        cache.invalidate_prefix('today_view')
        self.assertIsNone(cache.get_cached(cache_key('today_view', 'teacher:1')))
        self.assertIsNone(cache.get_cached(cache_key('today_view', 'teacher:2')))

    def test_cache_today_view_invalidation(self):
        key = cache_key('today_view', 'teacher:9')
        cache.set_cached(key, {'cached': True}, ttl=5)
        cache.invalidate(key)
        self.assertIsNone(cache.get_cached(key))

    def test_bypass_cache_flag(self):
        key = cache_key('admin_ops')
        counter = {'n': 0}

        @cached_view(ttl=60, key_builder=lambda **_: key)
        def handler(bypass_cache: bool = False):
            counter['n'] += 1
            return {'value': counter['n']}

        first = handler(bypass_cache=True)
        self.assertIsNone(cache.get_cached(key))
        second = handler()
        cached = cache.get_cached(key)
        self.assertIsNotNone(cached)
        self.assertEqual(second, cached)
        self.assertNotEqual(first, second)

    def test_multi_role_cache_keys(self):
        admin_key = cache_key('today_view', 'admin:all')
        teacher_key = cache_key('today_view', 'teacher:42')
        self.assertNotEqual(admin_key, teacher_key)


class RedisBackendTests(unittest.TestCase):
    def setUp(self):
        self._orig_redis = sys.modules.get('redis')

        class FakeRedisClient:
            def __init__(self):
                self._store = {}

            def setex(self, key, ttl, value):
                self._store[key] = (time.time() + ttl, value)

            def get(self, key):
                item = self._store.get(key)
                if not item:
                    return None
                expires_at, value = item
                if time.time() >= expires_at:
                    self._store.pop(key, None)
                    return None
                return value

            def delete(self, *keys):
                for key in keys:
                    self._store.pop(key, None)

            def scan(self, cursor=0, match='*', count=100):
                prefix = match[:-1] if match.endswith('*') else match
                keys = [key for key in self._store.keys() if key.startswith(prefix)]
                return 0, keys

        class FakeRedisModule:
            class Redis:
                @staticmethod
                def from_url(url, decode_responses=True):
                    return FakeRedisClient()

        sys.modules['redis'] = FakeRedisModule()

    def tearDown(self):
        if self._orig_redis is None:
            sys.modules.pop('redis', None)
        else:
            sys.modules['redis'] = self._orig_redis

    def test_redis_backend_roundtrip(self):
        backend = RedisCacheBackend('redis://localhost:6379/0')
        manager = CacheManager(backend=backend)
        manager.set_cached('admin_ops', {'ok': True}, ttl=5)
        self.assertEqual(manager.get_cached('admin_ops'), {'ok': True})


if __name__ == '__main__':
    unittest.main()
