"""Удалённый доступ: пароль, cookie, хосты, ограничение попыток."""
import os
import unittest
from unittest import mock

from backend import remote_access, test_smoke

ENV = {'STUDIO_REMOTE_HOSTS': 'studio.example.com', 'STUDIO_ACCESS_PASSWORD': 'correct-horse-battery'}
H = {'host': 'studio.example.com'}


class RemoteAccessTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def test_disabled_by_default_rejects_foreign_host(self):
        remote_access._fails.clear()
        r = self.client.get('/api/health', headers=H)
        self.assertEqual(r.status_code, 403)

    def test_login_flow(self):
        remote_access._fails.clear()
        with mock.patch.dict(os.environ, ENV):
            self.assertEqual(self.client.get('/api/projects', headers=H).status_code, 401)
            self.assertEqual(self.client.get('/', headers=H, follow_redirects=False).status_code, 307)
            self.assertEqual(self.client.get('/login', headers=H).status_code, 200)
            bad = self.client.post('/api/login', json={'password': 'nope'}, headers=H)
            self.assertEqual(bad.status_code, 401)
            ok = self.client.post('/api/login', json={'password': ENV['STUDIO_ACCESS_PASSWORD']},
                                  headers={**H, 'x-forwarded-proto': 'https'})
            self.assertEqual(ok.status_code, 200)
            self.assertIn('Secure', ok.headers['set-cookie'])
            cookie = ok.cookies.get('studio_auth')
            self.assertTrue(cookie)
            # с cookie входа сессионный токен выдаётся, обычные запросы работают
            session = self.client.get('/api/session', headers={**H, 'cookie': 'studio_auth=' + cookie})
            self.assertEqual(session.status_code, 200)

    def test_rate_limit_and_foreign_origin(self):
        remote_access._fails.clear()
        with mock.patch.dict(os.environ, ENV):
            for _ in range(remote_access.MAX_FAILS):
                self.client.post('/api/login', json={'password': 'x'}, headers=H)
            blocked = self.client.post('/api/login', json={'password': ENV['STUDIO_ACCESS_PASSWORD']}, headers=H)
            self.assertEqual(blocked.status_code, 429)
            evil = self.client.get('/api/health', headers={**H, 'origin': 'https://evil.example'})
            self.assertEqual(evil.status_code, 403)
        remote_access._fails.clear()

    def test_cookie_signature_and_short_password(self):
        value = remote_access.make_cookie('p' * 14)
        self.assertTrue(remote_access.valid_cookie(value, 'p' * 14))
        self.assertFalse(remote_access.valid_cookie(value, 'q' * 14))
        self.assertFalse(remote_access.valid_cookie(value + 'x', 'p' * 14))
        self.assertFalse(remote_access.valid_cookie(value, 'p' * 14, now=9e12))
        with mock.patch.dict(os.environ, {'STUDIO_REMOTE_HOSTS': 'a.example', 'STUDIO_ACCESS_PASSWORD': 'short'}):
            with self.assertRaises(RuntimeError):
                remote_access.config()


if __name__ == '__main__':
    unittest.main()
