import time
import unittest
from backend import main, reference_upload, test_smoke


class ReferenceUrlTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def test_only_public_https_counts_as_reference(self):
        public = reference_upload.public_https
        self.assertEqual(public('https://img.theapi.app/ephemeral/a.jpeg'), 'https://img.theapi.app/ephemeral/a.jpeg')
        for bad in ('inline-base64', 'data:image/png;base64,AAAA', 'http://tempfile.org/x', 'https://', '', None):
            self.assertIsNone(public(bad), bad)

    def test_library_hides_inline_base64_and_keeps_real_links(self):
        row = {'id': 'asset-inline', 'source_url': 'inline-base64'}
        self.assertIsNone(reference_upload.reference_url(main, row))
        self.assertEqual(
            reference_upload.reference_url(main, {'id': 'asset-real', 'source_url': 'https://img.theapi.app/e/1.png'}),
            'https://img.theapi.app/e/1.png',
        )

    def test_fresh_cached_upload_beats_inline_marker(self):
        with main.connect() as db:
            db.execute('INSERT INTO public_references(asset_id,url,expires_at,provider) VALUES(?,?,?,?)',
                       ('asset-cached', 'https://tempfile.org/abc/download', time.time() + 3600, 'tempfile'))
        row = {'id': 'asset-cached', 'source_url': 'inline-base64'}
        self.assertEqual(reference_upload.reference_url(main, row), 'https://tempfile.org/abc/download')
        with main.connect() as db:
            db.execute('UPDATE public_references SET expires_at=? WHERE asset_id=?', (time.time() - 1, 'asset-cached'))
        self.assertIsNone(reference_upload.reference_url(main, row))


if __name__ == '__main__':
    unittest.main()
