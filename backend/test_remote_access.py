"""Удалённый доступ: пароль, cookie, хосты, ограничение попыток."""
import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend import main, remote_access, test_smoke

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

class HomeNetworkTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown
    LAN = {'STUDIO_REMOTE_HOSTS': '192.168.8.253', 'STUDIO_ACCESS_PASSWORD': 'correct-horse-battery'}

    def test_spoofed_loopback_host_from_another_device_still_needs_login(self):
        class Req:
            headers = {'host': '127.0.0.1:8000'}
            client = type('C', (), {'host': '192.168.8.50'})()
        self.assertFalse(remote_access.is_loopback(Req()))
        Req.client = type('C', (), {'host': '127.0.0.1'})()
        self.assertTrue(remote_access.is_loopback(Req()))

    def test_tailscale_addresses_count_as_private(self):
        self.assertTrue(remote_access.private_ip('100.101.102.103'))
        self.assertFalse(remote_access.private_ip('8.8.8.8'))
        with mock.patch.dict(os.environ, {"STUDIO_REMOTE_HOSTS": "100.101.102.103", 'STUDIO_ACCESS_PASSWORD': 'correct-horse-battery'}):
            self.assertTrue(remote_access.allowed_origin('http://100.101.102.103:5173'))

    def test_http_origin_only_for_listed_private_ip_and_known_ports(self):
        with mock.patch.dict(os.environ, self.LAN):
            self.assertTrue(remote_access.allowed_origin('http://192.168.8.253:8000'))
            self.assertTrue(remote_access.allowed_origin('http://192.168.8.253'))
            self.assertFalse(remote_access.allowed_origin('http://192.168.8.253:9999'))
            self.assertFalse(remote_access.allowed_origin('http://192.168.8.77:8000'))
        with mock.patch.dict(os.environ, {'STUDIO_REMOTE_HOSTS': '8.8.8.8', 'STUDIO_ACCESS_PASSWORD': 'correct-horse-battery'}):
            self.assertFalse(remote_access.allowed_origin('http://8.8.8.8:8000'))


class TrustedProxyTests(unittest.TestCase):
    """GA-05: лимит попыток входа не обходится поддельным X-Forwarded-For."""

    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    BASE = {'STUDIO_REMOTE_HOSTS': 'studio.example.com', 'STUDIO_ACCESS_PASSWORD': 'correct-horse-battery',
            'STUDIO_TRUSTED_PROXIES': '', 'STUDIO_TRUSTED_PROXY_HOPS': ''}
    PROXY = dict(BASE, STUDIO_TRUSTED_PROXIES='10.0.0.1', STUDIO_TRUSTED_PROXY_HOPS='1')
    PEER = '198.51.100.7'      # прямой клиент, не proxy
    PROXY_PEER = '10.0.0.1'    # доверенный proxy

    @staticmethod
    def _request(peer, headers=None):
        class Req:
            pass
        req = Req()
        req.headers = headers or {}
        req.client = type('C', (), {'host': peer})()
        return req

    @staticmethod
    def _client(peer):
        return TestClient(main.app, base_url='http://127.0.0.1', client=(peer, 40000))

    def test_direct_peer_ignores_forwarded_for(self):
        with mock.patch.dict(os.environ, self.BASE):
            for forwarded in ('203.0.113.5', '203.0.113.5, 198.51.100.9', 'unknown', ''):
                req = self._request(self.PEER, {'x-forwarded-for': forwarded})
                self.assertEqual(remote_access.client_ip(req), self.PEER, forwarded)

    def test_spoofed_xff_does_not_bypass_rate_limit(self):
        remote_access._fails.clear()
        with mock.patch.dict(os.environ, self.BASE):
            client = self._client(self.PEER)
            codes = []
            for i in range(7):
                r = client.post('/api/login', json={'password': 'wrong'},
                                headers={**H, 'x-forwarded-for': f'203.0.113.{i}'})
                codes.append(r.status_code)
            self.assertEqual(codes, [401] * remote_access.MAX_FAILS + [429] * 2)
            self.assertEqual(list(remote_access._fails), [self.PEER])
        remote_access._fails.clear()

    def test_trusted_proxy_uses_forwarded_client(self):
        with mock.patch.dict(os.environ, self.PROXY):
            req = self._request(self.PROXY_PEER, {'x-forwarded-for': '203.0.113.5'})
            self.assertEqual(remote_access.client_ip(req), '203.0.113.5')

    def test_forged_chain_does_not_change_client_identity(self):
        with mock.patch.dict(os.environ, self.PROXY):
            for forged in ('198.51.100.9', '198.51.100.9, 198.51.100.10', '198.51.100.9, 10.0.0.1'):
                req = self._request(self.PROXY_PEER, {'x-forwarded-for': forged + ', 203.0.113.5'})
                self.assertEqual(remote_access.client_ip(req), '203.0.113.5', forged)

    def test_empty_and_malformed_chain_falls_back_to_peer(self):
        with mock.patch.dict(os.environ, self.PROXY):
            for forwarded in ('', '   ', 'unknown', 'not-an-ip', ',,,', '203.0.113.5:99999', '203.0.113.5:0'):
                req = self._request(self.PROXY_PEER, {'x-forwarded-for': forwarded})
                self.assertEqual(remote_access.client_ip(req), self.PROXY_PEER, forwarded)

    def test_chain_shorter_than_hop_count_falls_back_to_peer(self):
        env = dict(self.PROXY, STUDIO_TRUSTED_PROXY_HOPS='2')
        with mock.patch.dict(os.environ, env):
            short = self._request(self.PROXY_PEER, {'x-forwarded-for': '203.0.113.5'})
            self.assertEqual(remote_access.client_ip(short), self.PROXY_PEER)
            full = self._request(self.PROXY_PEER, {'x-forwarded-for': '203.0.113.5, 10.0.0.1'})
            self.assertEqual(remote_access.client_ip(full), '203.0.113.5')

    def test_two_trusted_hops_resolve_client(self):
        env = dict(self.BASE, STUDIO_TRUSTED_PROXIES='10.0.0.1,10.0.0.2', STUDIO_TRUSTED_PROXY_HOPS='2')
        with mock.patch.dict(os.environ, env):
            req = self._request('10.0.0.2', {'x-forwarded-for': '203.0.113.5, 10.0.0.1'})
            self.assertEqual(remote_access.client_ip(req), '203.0.113.5')

    def test_ipv4_and_ipv6_addresses(self):
        env = dict(self.BASE, STUDIO_TRUSTED_PROXIES='2001:db8::/32', STUDIO_TRUSTED_PROXY_HOPS='1')
        with mock.patch.dict(os.environ, env):
            req = self._request('2001:db8::1', {'x-forwarded-for': '2001:db8:1::5'})
            self.assertEqual(remote_access.client_ip(req), '2001:db8:1::5')
            bracketed = self._request('2001:db8::1', {'x-forwarded-for': '[2001:db8:1::6]'})
            self.assertEqual(remote_access.client_ip(bracketed), '2001:db8:1::6')
        with mock.patch.dict(os.environ, self.PROXY):
            mapped = self._request('::ffff:10.0.0.1', {'x-forwarded-for': '203.0.113.5'})
            self.assertEqual(remote_access.client_ip(mapped), '203.0.113.5')

    def test_trusted_proxy_throttle_is_per_client(self):
        remote_access._fails.clear()
        with mock.patch.dict(os.environ, self.PROXY):
            client = self._client(self.PROXY_PEER)
            for i in range(remote_access.MAX_FAILS):
                r = client.post('/api/login', json={'password': 'wrong'},
                                headers={**H, 'x-forwarded-for': f'198.51.100.{i}, 203.0.113.5'})
                self.assertEqual(r.status_code, 401)
            blocked = client.post('/api/login', json={'password': 'wrong'},
                                  headers={**H, 'x-forwarded-for': '203.0.113.5'})
            self.assertEqual(blocked.status_code, 429)
            other = client.post('/api/login', json={'password': 'wrong'},
                                headers={**H, 'x-forwarded-for': '203.0.113.6'})
            self.assertEqual(other.status_code, 401)
        remote_access._fails.clear()

    def test_correct_login_still_works_behind_trusted_proxy(self):
        remote_access._fails.clear()
        with mock.patch.dict(os.environ, self.PROXY):
            client = self._client(self.PROXY_PEER)
            ok = client.post('/api/login', json={'password': self.BASE['STUDIO_ACCESS_PASSWORD']},
                              headers={**H, 'x-forwarded-for': '203.0.113.5', 'x-forwarded-proto': 'https'})
            self.assertEqual(ok.status_code, 200)
            self.assertIn('Secure', ok.headers['set-cookie'])
            cookie = ok.cookies.get('studio_auth')
            self.assertTrue(cookie)
            session = client.get('/api/session', headers={**H, 'cookie': 'studio_auth=' + cookie})
            self.assertEqual(session.status_code, 200)
        remote_access._fails.clear()

    def test_spoofed_loopback_host_does_not_bypass_login(self):
        with mock.patch.dict(os.environ, self.BASE):
            client = self._client(self.PEER)
            r = client.get('/api/projects', headers={'host': '127.0.0.1:8000', 'x-forwarded-for': '127.0.0.1'})
            self.assertEqual(r.status_code, 401)

    def test_foreign_origin_still_rejected(self):
        with mock.patch.dict(os.environ, self.PROXY):
            client = self._client(self.PROXY_PEER)
            evil = client.get('/api/health', headers={**H, 'origin': 'https://evil.example'})
            self.assertEqual(evil.status_code, 403)

    def test_invalid_trusted_proxy_settings_are_rejected(self):
        with mock.patch.dict(os.environ, dict(self.BASE, STUDIO_TRUSTED_PROXIES='not-an-ip')):
            with self.assertRaises(RuntimeError):
                remote_access.trusted_proxies()
        with mock.patch.dict(os.environ, dict(self.BASE, STUDIO_TRUSTED_PROXY_HOPS='0')):
            with self.assertRaises(RuntimeError):
                remote_access.trusted_hops()
        with mock.patch.dict(os.environ, dict(self.BASE, STUDIO_TRUSTED_PROXY_HOPS='many')):
            with self.assertRaises(RuntimeError):
                remote_access.trusted_hops()


if __name__ == '__main__':
    unittest.main()
