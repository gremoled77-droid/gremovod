"""N34 — техническое QC: измерения, подпись, вердикт.

Без сети и без платных вызовов: ffprobe/ffmpeg работают с локальным тестовым
роликом, всё остальное — чистые функции.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import main, media_qc, security

FFMPEG = shutil.which('ffmpeg')
FFPROBE = shutil.which('ffprobe')


def sample_mp4(path: Path) -> Path:
    """Короткий тестовый ролик: 320x240, 10 кадров в секунду, одна секунда со звуком."""
    for codec in (['-c:v', 'libx264'], ['-c:v', 'mpeg4']):
        result = subprocess.run(
            [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y',
             '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=10:duration=1',
             '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
             *codec, '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(path)],
            capture_output=True, text=True, timeout=180)
        if result.returncode == 0 and path.is_file() and path.stat().st_size:
            return path
    raise unittest.SkipTest('FFmpeg не смог собрать тестовый ролик')


MASTER = {'width': 320, 'height': 240, 'fps': 10, 'duration_ms': 1000, 'container': 'mp4',
          'require_audio': True, 'duration_tolerance_ms': 400, 'fps_tolerance': 0.5}


def measurement(**overrides):
    master = {'duration_ms': 1000, 'format': 'mov,mp4,m4a,3gp,3g2,mj2', 'bitrate': 240000,
              'width': 320, 'height': 240, 'fps': 10.0, 'video_codec': 'h264', 'audio_codec': 'aac',
              'audio_streams': 1, 'sample_rate': 44100, 'decodes': True}
    master.update(overrides.pop('master', {}))
    return {'master': master, 'observations': overrides.pop('observations', {})}


class VerdictTests(unittest.TestCase):
    """Вердикт — чистая функция: один и тот же вход даёт один и тот же ответ."""

    def test_manifest_matched_gives_pass_technical(self):
        result = media_qc.verdict(measurement(), MASTER)
        self.assertEqual(result['status'], media_qc.PASS_TECHNICAL)
        self.assertTrue(all(check['ok'] for check in result['checks']))

    def test_width_mismatch_gives_fail(self):
        result = media_qc.verdict(measurement(master={'width': 1920}), MASTER)
        self.assertEqual(result['status'], media_qc.FAIL)
        self.assertFalse([check for check in result['checks'] if check['name'] == 'ширина'][0]['ok'])

    def test_duration_outside_tolerance_gives_fail(self):
        result = media_qc.verdict(measurement(master={'duration_ms': 9000}), MASTER)
        self.assertEqual(result['status'], media_qc.FAIL)

    def test_container_mismatch_gives_fail(self):
        result = media_qc.verdict(measurement(master={'format': 'matroska,webm'}), MASTER)
        self.assertEqual(result['status'], media_qc.FAIL)

    def test_missing_master_is_blocked(self):
        result = media_qc.verdict({'master': None, 'observations': {}}, MASTER)
        self.assertEqual(result['status'], media_qc.BLOCKED)
        self.assertIn('ffprobe', result['reason'])

    def test_required_audio_missing_is_blocked(self):
        result = media_qc.verdict(measurement(master={'audio_codec': '', 'audio_streams': 0}), MASTER)
        self.assertEqual(result['status'], media_qc.BLOCKED)
        self.assertIn('аудиодорожк', result['reason'])

    def test_undecodable_file_is_blocked(self):
        result = media_qc.verdict(measurement(master={'decodes': False}), MASTER)
        self.assertEqual(result['status'], media_qc.BLOCKED)
        self.assertIn('декодируется', result['reason'])

    def test_observations_do_not_change_the_verdict(self):
        noisy = measurement(observations={'black_intervals': [{'start_ms': 0, 'end_ms': 900}],
                                          'lufs_integrated': -40.0})
        self.assertEqual(media_qc.verdict(noisy, MASTER)['status'], media_qc.PASS_TECHNICAL)

    def test_observations_are_returned_even_when_blocked(self):
        result = media_qc.verdict(measurement(observations={'lufs_integrated': -23.0}, master={'decodes': False}), MASTER)
        self.assertEqual(result['status'], media_qc.BLOCKED)
        self.assertEqual(result['observations']['lufs_integrated'], -23.0)


class SignatureTests(unittest.TestCase):
    def test_valid_signature_is_accepted(self):
        report = {'artifact_id': 'a', 'master': {'width': 320}}
        self.assertTrue(security.qc_verify(report, security.qc_sign(report)))

    def test_tampered_report_is_rejected(self):
        report = {'artifact_id': 'a', 'master': {'width': 320}}
        signature = security.qc_sign(report)
        report['master']['width'] = 1920
        self.assertFalse(security.qc_verify(report, signature))

    def test_foreign_signature_is_rejected(self):
        report = {'artifact_id': 'a', 'master': {'width': 320}}
        self.assertFalse(security.qc_verify(report, 'deadbeef' * 8))


@unittest.skipUnless(FFMPEG and FFPROBE, 'FFmpeg не установлен')
class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [patch.object(main, 'DB', root / 'studio.sqlite3'),
                        patch.object(main, 'LIBRARY_ROOT', root / 'library'),
                        patch.object(main, 'PRODUCTIONS_ROOT', root / 'projects')]
        for item in self.patches:
            item.start()
        self.addCleanup(self.temp.cleanup)
        for item in self.patches:
            self.addCleanup(item.stop)
        self.client = TestClient(main.app, base_url='http://127.0.0.1')
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.client.headers['X-Studio-Session'] = self.client.get('/api/session').json()['token']
        self.project_id = self.client.post('/api/projects', json={'title': 'N34', 'state': {}}).json()['id']
        self.revision = self.client.get('/api/projects/' + self.project_id).json()['revision']
        self.video = sample_mp4(root / 'master.mp4')
        self.artifact_id = self.upload().json()['id']

    def upload(self):
        with self.video.open('rb') as source:
            return self.client.post('/api/projects/' + self.project_id + '/release-artifacts',
                                    data={'project_revision': str(self.revision), 'title': 'Выпуск'},
                                    files={'file': ('master.mp4', source, 'video/mp4')})

    def measure(self, manifest=None):
        return self.client.post(
            f'/api/projects/{self.project_id}/release-artifacts/{self.artifact_id}/qc/measure',
            json={'manifest': manifest if manifest is not None else MASTER})

    def test_measure_passes_technical_and_stores_verdict(self):
        response = self.measure()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['verdict'], media_qc.PASS_TECHNICAL)
        stored = self.client.get(f'/api/projects/{self.project_id}/release-artifacts/{self.artifact_id}/qc')
        self.assertEqual(stored.status_code, 200, stored.text)
        self.assertEqual(stored.json()['verdict'], media_qc.PASS_TECHNICAL)
        self.assertTrue(stored.json()['master_sha256'])

    def test_measure_detects_wrong_expectation(self):
        response = self.measure({**MASTER, 'width': 1920})
        self.assertEqual(response.json()['verdict'], media_qc.FAIL)

    def test_missing_file_is_blocked_not_an_error(self):
        Path(main.LIBRARY_ROOT, self.video.name).unlink(missing_ok=True)
        for name in main.LIBRARY_ROOT.glob('*'):
            if name.suffix == '.mp4':
                name.unlink(missing_ok=True)
        response = self.measure()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['verdict'], media_qc.BLOCKED)

    def test_worker_report_is_accepted(self):
        path = Path(main.LIBRARY_ROOT)
        stored_file = next(path.glob('*.mp4'))
        report = media_qc.build_report(self.project_id, self.artifact_id, stored_file,
                                       media_qc.measure(main.cmd, stored_file), MASTER)
        signature = security.qc_sign(report)
        response = self.client.post(f'/api/projects/{self.project_id}/release-artifacts/{self.artifact_id}/qc',
                                    json={'report': report, 'signature': signature, 'manifest': MASTER})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['verdict'], media_qc.PASS_TECHNICAL)

    def test_tampered_report_is_rejected(self):
        stored_file = next(Path(main.LIBRARY_ROOT).glob('*.mp4'))
        report = media_qc.build_report(self.project_id, self.artifact_id, stored_file,
                                       media_qc.measure(main.cmd, stored_file), MASTER)
        signature = security.qc_sign(report)
        report['master']['width'] = 1920
        response = self.client.post(f'/api/projects/{self.project_id}/release-artifacts/{self.artifact_id}/qc',
                                    json={'report': report, 'signature': signature, 'manifest': MASTER})
        self.assertEqual(response.status_code, 400, response.text)

    def test_report_with_foreign_hash_is_blocked(self):
        stored_file = next(Path(main.LIBRARY_ROOT).glob('*.mp4'))
        report = media_qc.build_report(self.project_id, self.artifact_id, stored_file,
                                       media_qc.measure(main.cmd, stored_file), MASTER)
        report['master_sha256'] = '0' * 64
        signature = security.qc_sign(report)
        response = self.client.post(f'/api/projects/{self.project_id}/release-artifacts/{self.artifact_id}/qc',
                                    json={'report': report, 'signature': signature, 'manifest': MASTER})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['verdict'], media_qc.BLOCKED)
        self.assertIn('хеш', response.json()['reason'])

    def test_report_for_another_artifact_is_rejected(self):
        stored_file = next(Path(main.LIBRARY_ROOT).glob('*.mp4'))
        report = media_qc.build_report(self.project_id, 'чужой-артефакт', stored_file,
                                       media_qc.measure(main.cmd, stored_file), MASTER)
        signature = security.qc_sign(report)
        response = self.client.post(f'/api/projects/{self.project_id}/release-artifacts/{self.artifact_id}/qc',
                                    json={'report': report, 'signature': signature, 'manifest': MASTER})
        self.assertEqual(response.status_code, 400, response.text)

    def test_file_changed_after_qc_does_not_inherit_the_verdict(self):
        """BETA-01: изменённый после QC файл не должен получать старый PASS при заморозке."""
        self.assertEqual(self.measure().json()['verdict'], media_qc.PASS_TECHNICAL)
        fresh = media_qc.master_facts(main, self.project_id, self.artifact_id)
        self.assertEqual(fresh['qc_verdict'], media_qc.PASS_TECHNICAL)
        with next(Path(main.LIBRARY_ROOT).glob('*.mp4')).open('ab') as stored:
            stored.write(b'tail')
        changed = media_qc.master_facts(main, self.project_id, self.artifact_id)
        self.assertEqual(changed['qc_verdict'], media_qc.BLOCKED)
        self.assertTrue(changed['qc_stale'])
        self.assertNotEqual(changed['sha256'], fresh['sha256'])

    def test_verdict_is_not_stored_without_a_check(self):
        response = self.client.get(f'/api/projects/{self.project_id}/release-artifacts/{self.artifact_id}/qc')
        self.assertEqual(response.status_code, 404, response.text)


if __name__ == '__main__':
    unittest.main()
