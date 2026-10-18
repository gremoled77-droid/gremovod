import io
import time
import unittest
from PIL import Image
from backend import main, reference_upload, test_smoke


class DeferredReferencesTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def request(self):
        pid = self.client.post('/api/projects', json={'title': 'Local references', 'state': {}}).json()['id']
        image = io.BytesIO()
        Image.new('RGB', (32, 24), 'blue').save(image, format='PNG')
        asset = self.client.post('/api/library/import-image', data={'project_id': pid},
                                 files={'file': ('local.png', image.getvalue(), 'image/png')}).json()
        main.PIAPI_KEY_FILE.write_text('test-piapi-key', encoding='utf-8')
        return {'project_id': pid, 'model_id': 'seedream-5-lite', 'prompt': 'Local reference',
                'reference_urls': [reference_upload.LOCAL_PREFIX + asset['id']],
                'request_id': 'deferred-reference-test-1234', 'approved': True, 'max_cost_usd': 1}

    def test_estimate_and_rejected_launch_never_upload(self):
        body = self.request()
        quote = self.client.post('/api/model-jobs/estimate', json=body)
        self.assertEqual(quote.status_code, 200, quote.text)
        for patch in ({'approved': False}, {'max_cost_usd': 0}, {'quote_token': 'invalid'}):
            result = self.client.post('/api/model-jobs', json={**body, 'quote_token': quote.json()['quote_token'], **patch})
            self.assertEqual(result.status_code, 400, result.text)
        reference_upload.upload_free.assert_not_awaited()
        main.request_piapi.assert_not_awaited()

    def test_confirmed_launch_resolves_refs_and_duplicate_never_resubmits(self):
        body = self.request()
        body['quote_token'] = self.client.post('/api/model-jobs/estimate', json=body).json()['quote_token']
        reference_upload.upload_free.side_effect = None
        reference_upload.upload_free.return_value = {'url': 'https://tempfile.org/test/download', 'expires_at': time.time()+3600}
        main.request_piapi.side_effect = None
        main.request_piapi.return_value = {'data': {'task_id': 'upstream-id', 'status': 'submitted'}}
        result = self.client.post('/api/model-jobs', json=body)
        self.assertEqual(result.status_code, 200, result.text)
        payload = main.request_piapi.call_args.args[3]
        self.assertNotIn(reference_upload.LOCAL_PREFIX, str(payload))
        self.assertIn('https://tempfile.org/test/download', str(payload))
        self.assertTrue(self.client.post('/api/model-jobs', json=body).json()['duplicate'])
        reference_upload.upload_free.assert_awaited_once()
        main.request_piapi.assert_awaited_once()

    def test_upload_failure_releases_reservation_and_never_submits_provider(self):
        body = self.request()
        body['quote_token'] = self.client.post('/api/model-jobs/estimate', json=body).json()['quote_token']
        reference_upload.upload_free.side_effect = main.HTTPException(502, 'Upload unavailable')
        result = self.client.post('/api/model-jobs', json=body)
        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.json()['detail']['status'], 'failed')
        main.request_piapi.assert_not_awaited()
        budget = self.client.get('/api/budgets/' + body['project_id']).json()
        self.assertEqual(budget['project_reserved_usd'], 0)

    def test_invalid_and_missing_local_reference_rejected_before_upload(self):
        body = self.request()
        for value in ('../escape', 'missing', 'missing?query=1'):
            result = self.client.post('/api/model-jobs/estimate', json={**body, 'reference_urls': [reference_upload.LOCAL_PREFIX+value]})
            self.assertIn(result.status_code, (400, 404), result.text)
        reference_upload.upload_free.assert_not_awaited()
