"""GA-03 — release gate: imported → technical_pass → owner_approved | rejected.

Без сети и платных вызовов: FFmpeg собирает синтетические ролики, остальное — локальный сервер.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import main, test_media_qc

OWNER = 'owner-test'
TOKEN = 'machine-gate-token'


@unittest.skipUnless(test_media_qc.FFMPEG and test_media_qc.FFPROBE, 'FFmpeg не установлен')
class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(main, 'DB', self.root / 'studio.sqlite3'),
                        patch.object(main, 'LIBRARY_ROOT', self.root / 'library'),
                        patch.object(main, 'PRODUCTIONS_ROOT', self.root / 'projects'),
                        patch.dict(os.environ, {'GREMOVOD_OWNER_ID': OWNER})]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(self.temp.cleanup)
        os.environ.pop('STUDIO_SERVICE_TOKENS', None)
        self.open_client()
        project = self.client.post('/api/projects', json={'title': 'GA-03', 'state': {'a': 1, 'b': 2}}).json()
        self.pid = project['id']
        self.video = test_media_qc.sample_mp4(self.root / 'master.mp4')
        self.aid = self.upload(self.video)['id']
        self.base = f'/api/projects/{self.pid}/release-artifacts/{self.aid}'

    def open_client(self):
        client = TestClient(main.app, base_url='http://127.0.0.1')
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        client.headers['X-Studio-Session'] = client.get('/api/session').json()['token']
        self.client = client

    def revision(self):
        return self.client.get('/api/projects/' + self.pid).json()['revision']

    def upload(self, path):
        with Path(path).open('rb') as source:
            response = self.client.post(f'/api/projects/{self.pid}/release-artifacts',
                                        data={'project_revision': str(self.revision()), 'title': 'Выпуск'},
                                        files={'file': ('master.mp4', source, 'video/mp4')})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def qc(self, manifest=None):
        response = self.client.post(self.base + '/qc/measure',
                                    json={'manifest': test_media_qc.MASTER if manifest is None else manifest})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def gate(self):
        response = self.client.get(self.base + '/gate')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def decide(self, decision='APPROVED', **overrides):
        body = {'decision': decision, 'owner_id': OWNER, 'processing_rights_confirmed': True,
                'expected_master_sha256': self.gate()['master_sha256'], 'note': ''}
        body.update(overrides)
        return self.client.post(self.base + '/decision', json=body)

    def stored(self):
        return next(self.main_library().glob('*.mp4'))

    def main_library(self):
        return main.LIBRARY_ROOT

    def assertCode(self, response, status, code):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.json()['detail']['code'], code, response.text)

    def approved(self):
        self.qc()
        response = self.decide()
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    # --- состояния ---------------------------------------------------------------------
    def test_import_is_imported_not_a_release(self):
        gate = self.gate()
        self.assertEqual(gate['state'], 'IMPORTED')
        self.assertEqual(len(gate['master_sha256']), 64)
        self.assertEqual(self.client.get(f'/api/projects/{self.pid}/release-artifacts').json()[0]['status'], 'imported')

    def test_technical_pass_then_owner_approved_bound_to_sha(self):
        self.qc()
        self.assertEqual(self.gate()['state'], 'TECHNICAL_PASS')
        data = self.approved()
        gate = data['gate']
        self.assertFalse(data['duplicate'])
        self.assertEqual(gate['state'], 'OWNER_APPROVED')
        self.assertEqual(gate['history'][0]['master_sha256'], gate['master_sha256'])
        self.assertEqual(gate['owner_id'], OWNER)
        self.assertTrue(gate['decided_at'])
        self.assertTrue(gate['n35_evidence']['processing_rights_confirmed'])

    def test_repeated_approval_creates_no_duplicate(self):
        self.approved()
        again = self.decide().json()
        self.assertTrue(again['duplicate'])
        self.assertEqual(len(self.gate()['history']), 1)

    def test_qc_fail_and_blocked_cannot_be_approved(self):
        self.qc({**test_media_qc.MASTER, 'width': 1920})
        self.assertCode(self.decide(), 409, 'QC_NOT_PASSED')
        silent = self.root / 'silent.mp4'
        subprocess.run([test_media_qc.FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i',
                        'testsrc=size=320x240:rate=10:duration=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(silent)],
                       check=True, timeout=120)
        self.aid = self.upload(silent)['id']
        self.base = f'/api/projects/{self.pid}/release-artifacts/{self.aid}'
        self.assertEqual(self.qc()['verdict'], 'BLOCKED')
        self.assertCode(self.decide(), 409, 'QC_NOT_PASSED')
        self.assertEqual(self.gate()['state'], 'IMPORTED')

    def test_approval_without_qc_is_refused(self):
        self.assertCode(self.decide(), 409, 'QC_NOT_RUN')

    def test_corrupt_file_is_not_imported(self):
        bad = self.root / 'bad.mp4'
        bad.write_bytes(b'not a video')
        with bad.open('rb') as source:
            response = self.client.post(f'/api/projects/{self.pid}/release-artifacts',
                                        data={'project_revision': str(self.revision())},
                                        files={'file': ('bad.mp4', source, 'video/mp4')})
        self.assertIn(response.status_code, (415, 422), response.text)

    def test_import_with_stale_project_revision_is_a_conflict(self):
        stale = self.revision()
        self.save_state({'a': 9})  # revision вырос
        with self.video.open('rb') as source:
            response = self.client.post(f'/api/projects/{self.pid}/release-artifacts',
                                        data={'project_revision': str(stale), 'title': 'Старый'},
                                        files={'file': ('master.mp4', source, 'video/mp4')})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()['detail']['code'], 'PROJECT_REVISION_CONFLICT')
        self.assertEqual(len(self.client.get(f'/api/projects/{self.pid}/release-artifacts').json()), 1)

    def test_revision_growth_alone_keeps_approval(self):
        self.approved()
        before = self.revision()
        self.save_state({'a': 1, 'b': 2})  # то же содержимое: revision растёт, якорь содержимого — нет
        self.assertGreater(self.revision(), before)
        self.assertEqual(self.gate()['state'], 'OWNER_APPROVED')

    # --- B1: байты изменены после QC ----------------------------------------------------
    def test_bytes_changed_after_qc_is_not_technical_pass(self):
        self.qc()
        with self.stored().open('ab') as handle:
            handle.write(b'\0tail')
        gate = self.gate()
        self.assertEqual(gate['state'], 'IMPORTED')
        self.assertTrue(gate['qc_stale'])
        self.assertCode(self.decide(), 409, 'QC_STALE')

    def test_bytes_changed_after_approval_revokes_it(self):
        self.approved()
        with self.stored().open('ab') as handle:
            handle.write(b'\0tail')
        gate = self.gate()
        self.assertNotEqual(gate['state'], 'OWNER_APPROVED')
        self.assertTrue(gate['decision_stale'])
        self.assertEqual(gate['decision_stale_code'], 'MASTER_CHANGED')

    def test_old_sha_from_the_screen_is_refused(self):
        self.qc()
        self.assertCode(self.decide(expected_master_sha256='0' * 64), 409, 'MASTER_CHANGED')
        self.assertCode(self.decide(expected_master_sha256=''), 409, 'MASTER_CHANGED')

    def test_missing_file_blocks_approval_but_not_rejection(self):
        self.qc()
        self.stored().unlink()
        self.assertCode(self.decide(), 409, 'MASTER_FILE_MISSING')
        rejected = self.decide('REJECTED', note='файл потерян', expected_master_sha256='')
        self.assertEqual(rejected.status_code, 200, rejected.text)
        self.assertEqual(rejected.json()['gate']['state'], 'REJECTED')

    def test_rerun_qc_fail_revokes_approval(self):
        self.approved()
        self.qc({**test_media_qc.MASTER, 'width': 1920})
        gate = self.gate()
        self.assertNotEqual(gate['state'], 'OWNER_APPROVED')
        self.assertEqual(gate['decision_stale_code'], 'QC_NOT_PASSED')

    # --- отказ -------------------------------------------------------------------------
    def test_reject_without_technical_pass_and_with_reason_stored(self):
        response = self.decide('REJECTED', note='плохой звук')
        self.assertEqual(response.status_code, 200, response.text)
        gate = response.json()['gate']
        self.assertEqual(gate['state'], 'REJECTED')
        self.assertEqual(gate['history'][0]['note'], 'плохой звук')
        self.assertTrue(self.decide('REJECTED', note='плохой звук').json()['duplicate'])
        self.assertEqual(len(self.gate()['history']), 1)

    def test_reject_requires_reason(self):
        response = self.decide('REJECTED', note='  ')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail']['code'], 'REJECT_REASON_REQUIRED')

    def test_approval_after_rejection_supersedes_and_keeps_history(self):
        self.qc()
        self.decide('REJECTED', note='не то')
        self.assertEqual(self.decide().json()['gate']['state'], 'OWNER_APPROVED')
        self.assertEqual([x['decision'] for x in self.gate()['history']], ['APPROVED', 'REJECTED'])

    def test_rejection_does_not_apply_to_changed_file(self):
        self.decide('REJECTED', note='не то')
        with self.stored().open('ab') as handle:
            handle.write(b'\0x')
        gate = self.gate()
        self.assertNotEqual(gate['state'], 'REJECTED')
        self.assertEqual(gate['decision_stale_code'], 'MASTER_CHANGED')

    # --- права, модальности, владелец --------------------------------------------------
    def test_processing_rights_required(self):
        self.qc()
        self.assertCode(self.decide(processing_rights_confirmed=False), 409, 'PROCESSING_RIGHTS_NOT_CONFIRMED')

    def test_required_audio_is_checked_by_n35(self):
        self.qc()
        # у синтетического ролика есть звук; неизвестная модальность N35 не подтверждает
        response = self.decide(required_modalities=['VIDEO', 'SUBTITLES'])
        self.assertCode(response, 409, 'MEDIA_NOT_CONFIRMED')

    def test_owner_must_be_configured_and_match(self):
        self.qc()
        self.assertCode(self.decide(owner_id='someone'), 409, 'OWNER_ID_MISMATCH')
        self.assertCode(self.decide(owner_id=''), 409, 'OWNER_ID_MISMATCH')
        os.environ['GREMOVOD_OWNER_ID'] = ''
        self.assertCode(self.decide(), 409, 'OWNER_ID_NOT_CONFIGURED')
        self.assertCode(self.decide('REJECTED', note='x'), 409, 'OWNER_ID_NOT_CONFIGURED')
        self.assertIn('OWNER_ID_NOT_CONFIGURED', [b['code'] for b in self.gate()['approve_blockers']])

    def test_owner_flag_in_body_cannot_replace_authentication(self):
        self.qc()
        response = self.decide(owner_approved=True, is_owner=True, state='OWNER_APPROVED')
        self.assertEqual(response.status_code, 200)  # лишние поля игнорируются; решает сервер
        self.assertEqual(len(self.gate()['history']), 1)

    def test_no_session_is_refused(self):
        self.qc()
        body = {'decision': 'APPROVED', 'owner_id': OWNER, 'processing_rights_confirmed': True,
                'expected_master_sha256': self.gate()['master_sha256']}
        anonymous = TestClient(main.app, base_url='http://127.0.0.1')
        self.addCleanup(anonymous.close)
        self.assertEqual(anonymous.post(self.base + '/decision', json=body).status_code, 401)

    def test_machine_token_cannot_decide(self):
        self.qc()
        os.environ['STUDIO_SERVICE_TOKENS'] = f'{TOKEN}:{self.pid}'
        self.addCleanup(os.environ.pop, 'STUDIO_SERVICE_TOKENS', None)
        body = {'decision': 'APPROVED', 'owner_id': OWNER, 'processing_rights_confirmed': True,
                'expected_master_sha256': self.gate()['master_sha256']}
        # токен + сессия: доходит до маршрута, маршрут отказывает сам
        both = self.client.post(self.base + '/decision', json=body, headers={'Authorization': f'Bearer {TOKEN}'})
        self.assertCode(both, 403, 'MACHINE_TOKEN_FORBIDDEN')
        reject = self.client.post(self.base + '/decision', json={**body, 'decision': 'REJECTED', 'note': 'x'},
                                  headers={'Authorization': f'Bearer {TOKEN}'})
        self.assertCode(reject, 403, 'MACHINE_TOKEN_FORBIDDEN')
        # токен без сессии: не пускает middleware
        bare = TestClient(main.app, base_url='http://127.0.0.1')
        self.addCleanup(bare.close)
        self.assertEqual(bare.post(self.base + '/decision', json=body, headers={'Authorization': f'Bearer {TOKEN}'}).status_code, 401)
        self.assertEqual(self.gate()['history'], [])

    def test_foreign_artifact_is_404(self):
        other = self.client.post('/api/projects', json={'title': 'Другой', 'state': {}}).json()['id']
        response = self.client.get(f'/api/projects/{other}/release-artifacts/{self.aid}/gate')
        self.assertEqual(response.status_code, 404)

    # --- содержимое проекта ------------------------------------------------------------
    def save_state(self, state, title='GA-03'):
        response = self.client.post('/api/projects', json={'id': self.pid, 'title': title, 'state': state,
                                                           'base_revision': self.revision()})
        self.assertEqual(response.status_code, 200, response.text)

    def test_cosmetic_changes_keep_approval(self):
        self.approved()
        self.save_state({'a': 1, 'b': 2}, title='Новое название')  # заголовок + рост revision
        self.assertEqual(self.gate()['state'], 'OWNER_APPROVED')
        self.save_state({'b': 2, 'a': 1})  # другой порядок ключей
        self.assertEqual(self.gate()['state'], 'OWNER_APPROVED')

    def test_content_change_revokes_approval(self):
        self.approved()
        self.save_state({'a': 1, 'b': 3})
        gate = self.gate()
        self.assertNotEqual(gate['state'], 'OWNER_APPROVED')
        self.assertEqual(gate['decision_stale_code'], 'CONTENT_CHANGED')
        # переутверждение одним действием
        self.assertEqual(self.decide().json()['gate']['state'], 'OWNER_APPROVED')

    # --- гонки и крайние случаи ---------------------------------------------------------
    def test_concurrent_identical_approvals_write_one_decision(self):
        import threading
        self.qc()
        body = {'decision': 'APPROVED', 'owner_id': OWNER, 'processing_rights_confirmed': True,
                'expected_master_sha256': self.gate()['master_sha256']}
        barrier = threading.Barrier(4)
        codes = []

        def go():
            barrier.wait()
            codes.append(self.client.post(self.base + '/decision', json=body).status_code)

        threads = [threading.Thread(target=go) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(codes, [200] * 4, codes)
        self.assertEqual(len(self.gate()['history']), 1)

    def test_file_swapped_between_hash_and_record_is_not_approved(self):
        from backend import release_gate
        self.qc()
        original = release_gate._record

        def swap_then_record(*args, **kwargs):
            with self.stored().open('ab') as handle:  # файл меняется после хеширования, до записи
                handle.write(b'\0swap')
            return original(*args, **kwargs)

        with patch.object(release_gate, '_record', swap_then_record):
            self.decide()
        gate = self.gate()
        self.assertNotEqual(gate['state'], 'OWNER_APPROVED')

    def test_invalid_decision_and_oversized_note_are_validation_errors(self):
        self.qc()
        self.assertEqual(self.decide('MAYBE').status_code, 422)
        self.assertEqual(self.decide('REJECTED', note='я' * 2001).status_code, 422)
        self.assertEqual(self.gate()['history'], [])

    def test_reject_note_is_stored_verbatim_unicode(self):
        note = 'Грэм <b>не</b> тот "кадр" — звук 🔊'
        self.assertEqual(self.decide('REJECTED', note=note).status_code, 200)
        self.assertEqual(self.gate()['history'][0]['note'], note)

    # --- кэш хеша только для чтения ----------------------------------------------------
    def digests(self):
        from backend import media_qc
        calls = []
        original = media_qc._digest

        def counting(path):
            calls.append(str(path))
            return original(path)

        return calls, patch.object(media_qc, '_digest', counting)

    def test_gate_reads_reuse_the_hash_of_an_unchanged_file(self):
        from backend import media_qc
        media_qc._HASH_CACHE.clear()
        self.qc()
        calls, counting = self.digests()
        with counting:
            first = self.gate()
            after_first = len(calls)
            second = self.gate()
        self.assertEqual(after_first, 1, calls)  # и master_facts, и N35 в одном чтении делят один хеш
        self.assertEqual(len(calls), after_first, 'второе чтение не должно хешировать файл')
        self.assertEqual(first['master_sha256'], second['master_sha256'])

    def test_cache_sees_appended_bytes_and_in_place_edits_with_restored_mtime(self):
        import os
        self.qc()
        before = self.gate()['master_sha256']
        path = self.stored()
        stat = path.stat()
        data = bytearray(path.read_bytes())
        data[len(data) // 2] ^= 0xFF  # тот же размер
        path.write_bytes(bytes(data))
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))  # mtime возвращён назад
        after = self.gate()
        self.assertNotEqual(after['master_sha256'], before)
        self.assertTrue(after['qc_stale'])

    def test_decisions_always_rehash_even_when_the_cache_is_warm(self):
        self.qc()
        self.gate()  # кэш прогрет
        calls, counting = self.digests()
        with counting:
            self.assertEqual(self.decide().status_code, 200)
        self.assertGreaterEqual(len(calls), 1)

    # --- перезапуск --------------------------------------------------------------------
    def test_state_survives_restart(self):
        self.approved()
        sha = self.gate()['master_sha256']
        self.client.__exit__(None, None, None)
        self.open_client()  # новый процесс-клиент над той же SQLite и библиотекой
        gate = self.gate()
        self.assertEqual(gate['state'], 'OWNER_APPROVED')
        self.assertEqual(gate['master_sha256'], sha)
        self.assertEqual(len(gate['history']), 1)


if __name__ == '__main__':
    unittest.main()
