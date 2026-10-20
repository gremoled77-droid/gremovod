"""N35 — заморозка медиа и evidence-манифест в QA-контуре.

Проверяем, что медиа-область становится подтверждённой только когда выполнено
всё условие, а три пакета критиков раздельны, но лежат на одном раунде и хеше.
Платные вызовы не выполняются; ffprobe/ffmpeg работают по локальному ролику.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import main, media_qc, qa_reviews, test_media_qc

TOKEN = 'qa-service-token'


@unittest.skipUnless(test_media_qc.FFMPEG and test_media_qc.FFPROBE, 'FFmpeg не установлен')
class FreezeMediaTests(unittest.TestCase):
    """Заморозка медиа: мастер, N34, права, покрытие модальностей."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [patch.object(main, 'DB', root / 'studio.sqlite3'),
                        patch.object(main, 'PRODUCTIONS_ROOT', root / 'projects'),
                        patch.object(main, 'LIBRARY_ROOT', root / 'library'),
                        patch.object(main, 'MEDIA', root / 'media')]
        for item in self.patches:
            item.start()
        self.addCleanup(self.temp.cleanup)
        for item in self.patches:
            self.addCleanup(item.stop)
        self.addCleanup(main.os.environ.pop, 'STUDIO_SERVICE_TOKENS', None)
        self.client = TestClient(main.app, base_url='http://127.0.0.1')
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.client.headers['X-Studio-Session'] = self.client.get('/api/session').json()['token']
        # Сначала браузерной сессией: проект, мастер, техническая проверка N34.
        # Машинный токен открывает только приёмочный контур /api/qa/*.
        self.pid = self.client.post('/api/projects', json={'title': 'N35', 'state': {}}).json()['id']
        self.revision = self.client.get('/api/projects/' + self.pid).json()['revision']
        self.video = test_media_qc.sample_mp4(root / 'master.mp4')
        with self.video.open('rb') as source:
            upload = self.client.post('/api/projects/' + self.pid + '/release-artifacts',
                                      data={'project_revision': str(self.revision), 'title': 'Выпуск'},
                                      files={'file': ('master.mp4', source, 'video/mp4')})
        self.assertEqual(upload.status_code, 200, upload.text)
        self.artifact_id = upload.json()['id']
        # Теперь машинный токен — только приёмочный контур.
        self.session_token = self.client.headers['X-Studio-Session']
        main.os.environ['STUDIO_SERVICE_TOKENS'] = f'{TOKEN}:{self.pid}'
        self.client.headers.pop('X-Studio-Session', None)
        self.client.cookies.clear()
        self.client.headers['Authorization'] = f'Bearer {TOKEN}'

    def qc(self):
        """Прогоняем N34 по мастеру: без него медиа не замораживается.

        Техническая проверка — обычный маршрут студии, машинный токен её не
        открывает, поэтому на время вызова возвращаем браузерную сессию.
        """
        self.client.headers['X-Studio-Session'] = self.session_token
        try:
            response = self.client.post(
                f'/api/projects/{self.pid}/release-artifacts/{self.artifact_id}/qc/measure',
                json={'manifest': {}})
        finally:
            self.client.headers.pop('X-Studio-Session', None)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def create_media_review(self, **extra):
        body = {'project_id': self.pid, 'task_id': 'task-media', 'artifact_id': 'artifact-media',
                'artifact_revision': 'rev-9', 'review_phase': 'FINAL_MEDIA',
                'requested_scopes': ['VIDEO', 'AUDIO'], 'request_id': 'qa-media-1',
                'media_asset_id': self.artifact_id, 'required_modalities': ['VIDEO', 'AUDIO'],
                'processing_rights_confirmed': True, **extra}
        response = self.client.post('/api/qa/reviews', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_media_is_confirmed_after_pass_technical(self):
        self.qc()
        data = self.create_media_review()
        self.assertEqual(data['media_status'], 'CONFIRMED', data['media_reason'])
        review = data['review']
        self.assertTrue(review['master_sha256'])
        self.assertTrue(review['snapshot_hash'])
        self.assertEqual(review['qc_verdict'], media_qc.PASS_TECHNICAL)

    def test_media_stays_blocked_without_pass_technical(self):
        data = self.create_media_review()
        self.assertNotEqual(data['media_status'], 'CONFIRMED')
        self.assertIn('N34', data['media_reason'])
        review = data['review']
        self.assertEqual(qa_reviews.trusted_sources(review, 'VIDEO'), [])

    def test_media_stays_blocked_without_processing_rights(self):
        self.qc()
        data = self.create_media_review(processing_rights_confirmed=False)
        self.assertNotEqual(data['media_status'], 'CONFIRMED')
        self.assertIn('право', data['media_reason'])

    def test_media_stays_blocked_for_unconfirmed_url(self):
        data = self.create_media_review(media_asset_id='', media_url='https://cdn.example.test/master.mp4')
        self.assertNotEqual(data['media_status'], 'CONFIRMED')
        self.assertIn('URL', data['media_reason'])

    def test_required_modality_without_track_is_blocked(self):
        self.qc()
        data = self.create_media_review(required_modalities=['AUDIO', 'UNKNOWN'])
        self.assertEqual(data['media_status'], 'PARTIAL', data['media_reason'])
        coverage = data['review']['evidence_manifest']['coverage']
        self.assertEqual(coverage['AUDIO']['status'], 'CONFIRMED')
        self.assertEqual(coverage['UNKNOWN']['status'], 'BLOCKED')

    def test_video_scope_gets_master_as_trusted_source(self):
        self.qc()
        review = self.create_media_review()['review']
        self.assertEqual(qa_reviews.trusted_sources(review, 'VIDEO'), [review['master_sha256']])

    def test_three_packets_are_separate_but_share_round_and_hash(self):
        self.qc()
        review = self.create_media_review()['review']
        packets = {}
        for role in ('REVIEW-REQ', 'REVIEW-SYSTEM', 'REVIEW-CRAFT'):
            response = self.client.get(f'/api/qa/reviews/{review["review_id"]}/packet/{role}')
            self.assertEqual(response.status_code, 200, response.text)
            packets[role] = response.json()
        ids = {packet['packet_id'] for packet in packets.values()}
        self.assertEqual(len(ids), 3, 'у критиков должны быть разные packet_id')
        hashes = {packet['snapshot_hash'] for packet in packets.values()}
        self.assertEqual(len(hashes), 1, 'все пакеты одного раунда делят один snapshot_hash')
        rounds = {packet['review_round'] for packet in packets.values()}
        self.assertEqual(rounds, {review['review_round']})
        for packet in packets.values():
            self.assertTrue(packet['packet_id'])

    def test_packet_does_not_contain_another_reviewers_verdict(self):
        self.qc()
        review = self.create_media_review()['review']
        review_id = review['review_id']
        verdict = self.client.post(f'/api/qa/reviews/{review_id}/verdicts', json={
            'role': 'REVIEW-REQ', 'verdict': 'FAIL', 'artifact_revision': 'rev-9',
            'checked_scopes': ['VIDEO'], 'scope_results': {'VIDEO': 'FAIL'}, 'evidence': [], 'request_id': 'v1'})
        self.assertEqual(verdict.status_code, 200, verdict.text)
        craft = self.client.get(f'/api/qa/reviews/{review_id}/packet/REVIEW-CRAFT').json()
        self.assertNotIn('FAIL', json.dumps(craft, ensure_ascii=False))
        self.assertNotIn('verdicts', craft)

    def test_packet_marks_stt_as_not_voice_evidence(self):
        self.qc()
        review = self.create_media_review(stt_transcript='Реплика из расшифровки.')['review']
        packet = self.client.get(f'/api/qa/reviews/{review["review_id"]}/packet/REVIEW-CRAFT').json()
        self.assertFalse(packet['evidence_policy']['stt_is_voice_evidence'])
        self.assertIn('тембр', packet['evidence_policy']['note'])
        self.assertEqual(packet['stt_transcript'], 'Реплика из расшифровки.')

    def test_packet_carries_frozen_media_evidence(self):
        self.qc()
        review = self.create_media_review()['review']
        packet = self.client.get(f'/api/qa/reviews/{review["review_id"]}/packet/REVIEW-CRAFT').json()
        self.assertEqual(packet['media']['status'], 'CONFIRMED')
        self.assertEqual(packet['trusted_revisions']['master_sha256'], review['master_sha256'])

    def test_verdict_on_media_scope_requires_trusted_source(self):
        self.qc()
        review = self.create_media_review()['review']
        response = self.client.post(f'/api/qa/reviews/{review["review_id"]}/verdicts', json={
            'role': 'REVIEW-CRAFT', 'verdict': 'PASS', 'artifact_revision': 'rev-9',
            'checked_scopes': ['VIDEO'], 'scope_results': {'VIDEO': 'PASS'},
            'evidence': [{'scope': 'VIDEO', 'evidence_type': 'video_frame',
                          'source_asset_id': review['master_sha256']}], 'request_id': 'v2'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['verdict']['scope_results']['VIDEO'], 'PASS')

    def test_verdict_without_trusted_media_source_stays_blocked(self):
        self.qc()
        review = self.create_media_review()['review']
        response = self.client.post(f'/api/qa/reviews/{review["review_id"]}/verdicts', json={
            'role': 'REVIEW-CRAFT', 'verdict': 'PASS', 'artifact_revision': 'rev-9',
            'checked_scopes': ['VIDEO'], 'scope_results': {'VIDEO': 'PASS'},
            'evidence': [{'scope': 'VIDEO', 'evidence_type': 'video_frame',
                          'source_asset_id': 'чужой-хеш'}], 'request_id': 'v3'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['verdict']['scope_results']['VIDEO'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
