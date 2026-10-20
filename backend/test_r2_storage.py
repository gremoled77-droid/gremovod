"""R2-хранилище: подпись запросов, ключи, публичные ссылки. Сеть не используется."""
import hashlib
import json
import unittest

from backend import r2_storage

CFG = {
    'endpoint': 'https://account.r2.cloudflarestorage.com',
    'bucket': 'gremovod',
    'access_key_id': 'AKIATEST',
    'secret_access_key': 'secret-test',
    'public_base_url': 'https://assets.grem.win',
}


class FakeTransport:
    """Записывает запрос и отдаёт заранее заданный ответ."""

    def __init__(self, status=200, body=b'', headers=None):
        self.status = status
        self.body = body
        self.headers = headers or {}
        self.calls = []

    def __call__(self, method, url, headers, payload):
        self.calls.append({'method': method, 'url': url, 'headers': headers, 'payload': payload})
        return type('Resp', (), {'status_code': self.status, 'text': 'err',
                                 'content': self.body, 'headers': self.headers})()


class R2StorageTests(unittest.TestCase):
    def test_authorization_has_alg_scope_and_signature(self):
        headers = r2_storage.sign_request('PUT', 'https://h/bucket/key', {}, 'UNSIGNED-PAYLOAD',
                                           'AKIA', 'secret')
        auth = headers['Authorization']
        self.assertTrue(auth.startswith('AWS4-HMAC-SHA256 Credential=AKIA/'))
        self.assertIn('/auto/s3/aws4_request', auth)
        self.assertIn('SignedHeaders=', auth)
        self.assertIn('Signature=', auth)

    def test_signature_changes_with_body(self):
        base = 'https://h/bucket/key'
        a = r2_storage.sign_request('PUT', base, {}, 'UNSIGNED-PAYLOAD', 'AKIA', 'secret')
        b = r2_storage.sign_request('PUT', base, {}, hashlib.sha256(b'x').hexdigest(), 'AKIA', 'secret')
        self.assertNotEqual(a['Authorization'], b['Authorization'])

    def test_canonical_uri_keeps_slashes_and_escapes_spaces(self):
        self.assertEqual(r2_storage.canonical_uri('images/hero main.png'), '/images/hero%20main.png')
        self.assertEqual(r2_storage.canonical_uri('a/b/c.webp'), '/a/b/c.webp')

    def test_public_url_uses_public_base(self):
        self.assertEqual(r2_storage.public_url(CFG, 'images/a.png'), 'https://assets.grem.win/images/a.png')

    def test_public_url_falls_back_to_s3_address(self):
        cfg = dict(CFG, public_base_url='')
        self.assertEqual(r2_storage.public_url(cfg, 'images/a.png'),
                         'https://account.r2.cloudflarestorage.com/gremovod/images/a.png')

    def test_put_bytes_sends_signed_request(self):
        transport = FakeTransport()
        url = r2_storage.put_bytes(CFG, 'images/a.png', b'hello', transport=transport)
        self.assertEqual(url, 'https://assets.grem.win/images/a.png')
        call = transport.calls[0]
        self.assertEqual(call['method'], 'PUT')
        self.assertTrue(call['url'].endswith('/gremovod/images/a.png'))
        self.assertEqual(call['payload'], b'hello')
        self.assertEqual(call['headers']['content-type'], 'image/png')
        self.assertEqual(call['headers']['x-amz-content-sha256'], hashlib.sha256(b'hello').hexdigest())
        self.assertIn('Authorization', call['headers'])

    def test_put_bytes_sets_content_type_by_suffix(self):
        transport = FakeTransport()
        r2_storage.put_bytes(CFG, 'web/x.webp', b'x', transport=transport)
        self.assertEqual(transport.calls[0]['headers']['content-type'], 'image/webp')

    def test_head_reports_size_and_missing_object(self):
        ok = FakeTransport(status=200, headers={'content-length': '42', 'etag': '"abc"'})
        self.assertEqual(r2_storage.head(CFG, 'x.png', transport=ok), {'size': 42, 'etag': 'abc'})
        missing = FakeTransport(status=404, body=b'not found')
        self.assertIsNone(r2_storage.head(CFG, 'x.png', transport=missing))

    def test_error_carries_status(self):
        transport = FakeTransport(status=403, body=b'forbidden')
        with self.assertRaises(r2_storage.R2Error) as ctx:
            r2_storage.put_bytes(CFG, 'x.png', b'x', transport=transport)
        self.assertIn('403', str(ctx.exception))

    def test_enabled_requires_full_config(self):
        self.assertTrue(r2_storage.enabled(CFG))
        self.assertFalse(r2_storage.enabled(dict(CFG, secret_access_key='')))
        self.assertFalse(r2_storage.enabled(dict(CFG, endpoint='')))

    def test_config_reads_environment(self):
        import os
        from unittest.mock import patch
        env = {'R2_ENDPOINT': 'https://x.r2.cloudflarestorage.com/', 'R2_BUCKET': 'b',
               'R2_ACCESS_KEY_ID': 'k', 'R2_SECRET_ACCESS_KEY': 's', 'R2_PUBLIC_BASE_URL': 'https://p/'}
        with patch.dict(os.environ, env, clear=False):
            cfg = r2_storage.config()
        self.assertEqual(cfg['endpoint'], 'https://x.r2.cloudflarestorage.com')
        self.assertEqual(cfg['public_base_url'], 'https://p')


class ManifestTests(unittest.TestCase):
    def test_manifest_lists_key_size_and_hash(self):
        from scripts import r2_upload
        import hashlib as _h
        data = b'payload'
        item = {'key': 'images/a.png', 'bytes': len(data), 'sha256': _h.sha256(data).hexdigest(),
                'content_type': 'image/png', 'url': 'https://assets.grem.win/images/a.png'}
        manifest = {'bucket': 'gremovod', 'prefix': 'demo', 'objects': [item]}
        text = json.dumps(manifest, ensure_ascii=False, indent=2)
        self.assertIn('"key": "images/a.png"', text)
        self.assertEqual(json.loads(text)['objects'][0]['sha256'], item['sha256'])


if __name__ == '__main__':
    unittest.main()
