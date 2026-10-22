"""BETA-02: точная проверка SHA в сборщике и гейте, очистка секретов из окружения pytest.

Всё на временном git-репозитории и временных папках: без сети и без реальных ключей.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import beta02_candidate as candidate  # noqa: E402
import beta_offline_acceptance as gate  # noqa: E402

CANARY = 'sk-canary0123456789abcdef'


def run(args, cwd):
    done = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, 'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@localhost',
                               'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@localhost'})
    if done.returncode:
        raise AssertionError(done.stderr)
    return done.stdout.strip()


class Repo:
    """Репозиторий: база, две ветки-источника и ссылки origin/* как после git fetch."""

    def __init__(self, root: Path):
        self.root = root
        run(['git', 'init', '-q', '-b', 'work', str(root)], root.parent)
        self.commit('base.txt', 'base')
        self.base = self.head()
        run(['git', 'checkout', '-q', '-b', 'a'], root)
        self.a = self.commit('a.txt', 'a')
        run(['git', 'checkout', '-q', '-b', 'b', self.base], root)
        self.b = self.commit('b.txt', 'b')
        run(['git', 'checkout', '-q', 'work'], root)
        for branch, sha in (('work', self.base), ('a', self.a), ('b', self.b)):
            run(['git', 'update-ref', f'refs/remotes/origin/{branch}', sha], root)

    def commit(self, name, text):
        (self.root / name).write_text(text, encoding='utf-8')
        run(['git', 'add', name], self.root)
        run(['git', 'commit', '-q', '-m', name], self.root)
        return self.head()

    def head(self):
        return run(['git', 'rev-parse', 'HEAD'], self.root)

    def manifest(self, **override):
        data = {'version': 1, 'base': {'branch': 'work', 'sha': self.base},
                'sources': [{'pr': 1, 'branch': 'a', 'sha': self.a, 'role': 'A'},
                            {'pr': 2, 'branch': 'b', 'sha': self.b, 'role': 'B'}]}
        data.update(override)
        path = self.root.parent / 'sources.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        return path


class ManifestTests(unittest.TestCase):
    def manifest(self, *sources, base='a' * 40):
        return {'version': 1, 'base': {'branch': 'work', 'sha': base}, 'sources': list(sources)}

    def test_valid_manifest_has_no_errors(self):
        self.assertEqual(candidate.manifest_errors(self.manifest({'pr': 1, 'branch': 'x', 'sha': 'b' * 40})), [])

    def test_short_uppercase_and_repeated_sha_are_rejected(self):
        bad = [self.manifest({'pr': 1, 'branch': 'x', 'sha': 'b' * 12}),
               self.manifest({'pr': 1, 'branch': 'x', 'sha': 'B' * 40}),
               self.manifest({'pr': 1, 'branch': 'x', 'sha': 'b' * 40}, {'pr': 2, 'branch': 'y', 'sha': 'b' * 40}),
               self.manifest({'pr': 1, 'branch': 'x', 'sha': 'a' * 40}),  # совпадает с базой
               self.manifest({'pr': 1, 'branch': 'x', 'sha': 'b' * 40}, {'pr': 1, 'branch': 'y', 'sha': 'c' * 40}),
               self.manifest({'pr': 1, 'branch': 'x', 'sha': 'b' * 40}, base='HEAD'),
               self.manifest(), {'version': 2}]
        for manifest in bad:
            self.assertTrue(candidate.manifest_errors(manifest), manifest)

    def test_unreadable_manifest_is_an_error_not_an_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'm.json'
            path.write_text('{not json', encoding='utf-8')
            self.assertTrue(candidate.load_manifest(path)[1])
            self.assertTrue(candidate.load_manifest(Path(tmp) / 'absent.json')[1])


class ExactShaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Repo(Path(self.tmp.name) / 'repo')
        self.dest = Path(self.tmp.name) / 'candidate'
        self.addCleanup(lambda: subprocess.run(['git', 'worktree', 'remove', '--force', str(self.dest)],
                                               cwd=self.repo.root, capture_output=True))

    def build(self, **kwargs):
        return candidate.build(self.dest, kwargs.pop('sources', None) or self.repo.manifest(), root=self.repo.root, **kwargs)

    def test_clean_build_contains_every_pinned_sha_and_the_gate_accepts_it(self):
        log = self.build()
        self.assertEqual(log['status'], 'OK', log)
        self.assertEqual([m['result'] for m in log['merges']], ['CLEAN', 'CLEAN'])
        info, problems = gate.provenance(self.repo.manifest(), root=self.dest)
        self.assertEqual(problems, [])
        self.assertTrue(all(s['in_tree'] and s['drift'] is False for s in info['sources']))

    def test_drift_stops_the_build_and_blocks_the_gate(self):
        run(['git', 'checkout', '-q', 'a'], self.repo.root)
        newer = self.repo.commit('a2.txt', 'a2')
        run(['git', 'checkout', '-q', 'work'], self.repo.root)
        run(['git', 'update-ref', 'refs/remotes/origin/a', newer], self.repo.root)
        log = self.build()
        self.assertEqual(log['status'], 'DRIFT')
        self.assertFalse(self.dest.exists())
        self.assertTrue(any('дрейф' in error for error in log['errors']))
        self.assertEqual(self.build(allow_drift=True)['status'], 'OK')  # воспроизведение — только явным флагом
        _, problems = gate.provenance(self.repo.manifest(), root=self.dest)
        self.assertTrue(any('дрейф' in problem for problem in problems))

    def test_missing_remote_ref_is_unverified_not_green(self):
        run(['git', 'update-ref', '-d', 'refs/remotes/origin/b'], self.repo.root)
        self.assertEqual(self.build()['status'], 'DRIFT')
        _, problems = gate.provenance(self.repo.manifest(), root=self.repo.root)
        self.assertTrue(any('нет ссылки origin/b' in problem for problem in problems))

    def test_unknown_commit_is_an_error_not_a_conflict(self):
        sources = self.repo.manifest(sources=[{'pr': 1, 'branch': 'a', 'sha': 'f' * 40, 'role': 'A'}])
        log = self.build(sources=sources)
        self.assertEqual(log['status'], 'ERROR')
        self.assertFalse(self.dest.exists())

    def test_short_harness_sha_is_rejected(self):
        self.assertEqual(self.build(harness=self.repo.a[:12])['status'], 'INVALID')

    def test_harness_is_merged_last_and_verified(self):
        run(['git', 'checkout', '-q', '-b', 'h', self.repo.base], self.repo.root)
        harness = self.repo.commit('h.txt', 'h')
        run(['git', 'checkout', '-q', 'work'], self.repo.root)
        log = self.build(harness=harness)
        self.assertEqual(log['status'], 'OK', log)
        self.assertEqual(log['merges'][-1], {'pr': 'harness', 'sha': harness, 'result': 'CLEAN'})

    def test_conflict_is_reported_with_files(self):
        run(['git', 'checkout', '-q', 'b'], self.repo.root)
        clash = self.repo.commit('a.txt', 'другое содержимое')
        run(['git', 'checkout', '-q', 'work'], self.repo.root)
        run(['git', 'update-ref', 'refs/remotes/origin/b', clash], self.repo.root)
        sources = self.repo.manifest(sources=[{'pr': 1, 'branch': 'a', 'sha': self.repo.a, 'role': 'A'},
                                              {'pr': 2, 'branch': 'b', 'sha': clash, 'role': 'B'}])
        log = self.build(sources=sources)
        self.assertEqual((log['status'], log['merges'][-1]['files']), ('CONFLICT', ['a.txt']))

    def test_gate_blocks_a_tree_without_a_source_and_a_dirty_tree(self):
        _, problems = gate.provenance(self.repo.manifest(), root=self.repo.root)  # HEAD = база
        self.assertTrue(any('#1' in p and 'отсутствует в HEAD' in p for p in problems))
        self.assertEqual(self.build()['status'], 'OK')
        (self.dest / 'stray.txt').write_text('x', encoding='utf-8')
        _, problems = gate.provenance(self.repo.manifest(), root=self.dest)
        self.assertTrue(any('грязное' in p for p in problems))


class SecretScrubTests(unittest.TestCase):
    BASE = {'PATH': os.environ.get('PATH', ''), 'LANG': 'ru_RU.UTF-8', 'HOME': '/home/owner', 'USERPROFILE': 'C:/Users/owner',
            'PIAPI_API_KEY': CANARY, 'OPENAI_API_KEY': CANARY + 'o', 'GITHUB_TOKEN': 'ghp_canary000000',
            'STUDIO_SERVICE_TOKENS': 'tok:*', 'GREMOVOD_QC_SIGNING_KEY': 'qc-canary-key', 'ELEVENLABS_KEY_FILE': '/home/owner/k.txt',
            'KIE_DPAPI_FILE': '/home/owner/kie.dpapi', 'DB_PASSWORD': 'hunter2-canary', 'AWS_SECRET_ACCESS_KEY': 'aws-canary-1',
            'HTTPS_PROXY': 'http://user:pw@proxy:3128', 'GIT_DIR': '/elsewhere', 'PYTHONSTARTUP': '/home/owner/s.py'}

    def test_only_allowlisted_variables_reach_pytest(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, removed, values = gate.child_env(self.BASE, Path(tmp), {'STUDIO_DATA_DIR': '/x'})
        for name in ('PIAPI_API_KEY', 'OPENAI_API_KEY', 'GITHUB_TOKEN', 'STUDIO_SERVICE_TOKENS', 'GREMOVOD_QC_SIGNING_KEY',
                     'KIE_DPAPI_FILE', 'DB_PASSWORD', 'AWS_SECRET_ACCESS_KEY', 'HTTPS_PROXY', 'GIT_DIR', 'PYTHONSTARTUP'):
            self.assertNotIn(name, env)
        self.assertEqual((env['PATH'], env['LANG'], env['STUDIO_DATA_DIR']), (self.BASE['PATH'], 'ru_RU.UTF-8', '/x'))
        self.assertNotIn('owner', env['HOME'] + env['USERPROFILE'])  # песочница, не настоящий профиль
        self.assertNotIn('owner', env['ELEVENLABS_KEY_FILE'])
        self.assertIn('PIAPI_API_KEY', removed)
        self.assertEqual(gate.scrub({'PWD': '/x', 'OLDPWD': '/y', 'DB_PWD': 'secret-pwd'})[1], ['DB_PWD'])  # PWD — папка
        self.assertIn(CANARY, values)
        self.assertNotIn(CANARY, json.dumps(env))

    def test_real_child_process_sees_no_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, _, _ = gate.child_env({**os.environ, **self.BASE, 'PATH': os.environ.get('PATH', '')}, Path(tmp), {})
            out = subprocess.run([sys.executable, '-c', 'import os, json, pathlib; '
                                  'print(json.dumps({"env": dict(os.environ), "home": str(pathlib.Path.home())}))'],
                                 env=env, capture_output=True, text=True).stdout
        seen = json.loads(out)
        for value in (CANARY, 'ghp_canary000000', 'hunter2-canary', 'aws-canary-1', 'qc-canary-key', 'tok:*'):
            self.assertNotIn(value, out)
        self.assertTrue(seen['home'].startswith(str(Path(tmp))))

    def test_report_masks_secret_values_and_key_like_strings(self):
        lines = gate.redact([f'boom {CANARY}', 'Authorization: Bearer abc.def', 'api_key=XYZ123 token: t0k3n',
                             'value hunter2-canary leaked'], ['hunter2-canary'])
        text = '\n'.join(lines)
        for value in (CANARY, 'abc.def', 'XYZ123', 't0k3n', 'hunter2-canary'):
            self.assertNotIn(value, text)
        self.assertIn('api_key=<secret>', text)

    def test_key_files_in_the_tree_are_found_without_reading_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(gate.key_files(root), [])
            (root / 'PIAPI_API_KEY.txt').write_text(CANARY, encoding='utf-8')
            (root / 'kie-access').mkdir()
            (root / 'kie-access' / 'api-key.dpapi').write_text('x', encoding='utf-8')
            (root / '.env.local').write_text('x', encoding='utf-8')
            (root / '.env.example').write_text('PIAPI_API_KEY=', encoding='utf-8')  # шаблон без значений — не ключ
            (root / '.env.cloud.example').write_text('x', encoding='utf-8')
            self.assertEqual(gate.key_files(root), ['.env.local', 'PIAPI_API_KEY.txt', 'kie-access/api-key.dpapi'])


if __name__ == '__main__':
    unittest.main()
