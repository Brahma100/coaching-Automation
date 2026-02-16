import unittest

from app.cache import cache, cache_key
from app.services.center_scope_service import center_context


class CacheIsolationTests(unittest.TestCase):
    def setUp(self):
        with center_context(101):
            cache.invalidate_prefix('today_view')
            cache.invalidate_prefix('admin_ops')
        with center_context(202):
            cache.invalidate_prefix('today_view')
            cache.invalidate_prefix('admin_ops')

    def test_center_scoped_cache_keys_do_not_overlap(self):
        key = cache_key('today_view', 'teacher:7')
        with center_context(101):
            cache.set_cached(key, {'center_id': 101, 'value': 'A'}, ttl=30)
        with center_context(202):
            self.assertIsNone(cache.get_cached(key))
            cache.set_cached(key, {'center_id': 202, 'value': 'B'}, ttl=30)

        with center_context(101):
            self.assertEqual(cache.get_cached(key)['value'], 'A')
        with center_context(202):
            self.assertEqual(cache.get_cached(key)['value'], 'B')

        backend = cache.backend
        store = getattr(backend, '_store', None)
        if isinstance(store, dict):
            keys = list(store.keys())
            self.assertTrue(any(str(k).startswith('center:101:') for k in keys))
            self.assertTrue(any(str(k).startswith('center:202:') for k in keys))

    def test_payload_center_mismatch_not_cached(self):
        key = cache_key('admin_ops', 'admin:9')
        with center_context(101):
            cache.set_cached(key, {'center_id': 202, 'value': 'leak'}, ttl=30)
            self.assertIsNone(cache.get_cached(key))

    def test_explicit_cross_center_lookup_logs_and_blocks(self):
        key = cache_key('today_view', 'teacher:9')
        with center_context(101):
            cache.set_cached(key, {'center_id': 101, 'value': 'only-A'}, ttl=30)
        with center_context(202):
            with self.assertLogs('app.cache', level='ERROR') as logs:
                value = cache.get_cached(f'center:101:{key}')
            self.assertIsNone(value)
            self.assertTrue(any('cache_center_mismatch_detected' in line for line in logs.output))


if __name__ == '__main__':
    unittest.main()
