import sqlite3, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import main, llm_guard

class Restart(unittest.TestCase):
    def test_restart_and_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'studio.sqlite3'
            with patch.object(main, 'DB', db_path), patch.object(main, 'PRODUCTIONS_ROOT', Path(tmp) / 'p'):
                with TestClient(main.app, base_url='http://127.0.0.1') as c:   # 1: создаёт схему
                    c.headers['X-Studio-Session'] = c.get('/api/session').json()['token']
                    pid = c.post('/api/projects', json={'title': 'legacy', 'state': {}}).json()['id']
                raw = sqlite3.connect(db_path)
                cols = [r[1] for r in raw.execute('PRAGMA table_info(llm_calls)')]
                print('columns', cols)
                def add(i, status, usd, est, tin=None, tout=None):
                    v = {'id': i, 'request_id': i + 'req00001', 'project_id': pid, 'model': 'gpt-5.6-luna', 'status': status, 'usd': usd,
                         'estimated_usd': est, 'input_tokens': tin, 'output_tokens': tout, 'created_at': main.now(), 'note': 'старая заметка'}
                    use = [k for k in cols if k in v]
                    raw.execute('INSERT INTO llm_calls(%s) VALUES(%s)' % (','.join(use), ','.join('?' * len(use))), [v[k] for k in use])
                add('neg-est', 'reserved', -0.1, 0.25)            # восстановим по оценке
                add('neg-bad', 'reserved', -0.1, 'bad')           # нечем верить -> unreadable
                add('text-usd', 'submission_unknown', 'junk', 0.0, 1000, 100)  # по токенам
                add('done-gap', 'done', 0.5, 0.5)
                raw.commit(); raw.close()
                snaps = []
                for n in range(3):                                # 3 запуска подряд = повторные миграции
                    with TestClient(main.app, base_url='http://127.0.0.1') as c:
                        health = c.get('/api/health').status_code
                    raw = sqlite3.connect(db_path); raw.row_factory = sqlite3.Row
                    snaps.append({r['id']: (r['status'], r['usd'], r['confirmed_usd'], r['note']) for r in raw.execute('SELECT * FROM llm_calls')}); raw.close()
                    print('start', n + 1, 'health', health)
                for k, v in snaps[0].items(): print(' ', k, v[:3], '| note:', (v[3] or '')[:110])
                self.assertEqual(snaps[0], snaps[1]); self.assertEqual(snaps[1], snaps[2], 'повторный запуск меняет записи')
                self.assertEqual(snaps[0]['neg-bad'][1], llm_guard.UNREADABLE_AMOUNT)
                self.assertEqual(snaps[0]['text-usd'][0], 'submission_unknown')
unittest.main() if __name__ == '__main__' else None
