import subprocess
import tempfile
import unittest
from pathlib import Path
from scripts.n8n_skill_sync import plan


class SkillSyncTests(unittest.TestCase):
    def test_pinned_references_stable_ids_dedup_and_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'skills' / 'sample'
            (folder / 'references').mkdir(parents=True)
            (folder / 'SKILL.md').write_text('---\nname: sample\ndescription: Test\n---\n[Test](references/test.md)\n', encoding='utf-8')
            ref = folder / 'references/test.md'
            ref.write_text('First reference', encoding='utf-8')
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()
            git('init')
            git('add', 'skills')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.test', '-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'Fixture')
            commit = git('rev-parse', 'HEAD')
            manifest = {'agents': [{'id': 'agent-1', 'skills': [{'name': 'sample', 'source': 'https://github.com/gremoled77-droid/gremovod/blob/main/skills/sample/SKILL.md'}]}]}
            result = plan(root, commit, manifest, [])['changes'][0]
            self.assertEqual(result['action'], 'bind_existing')
            self.assertEqual(len(result['files']), 2)
            binding = {'agent_id': 'agent-1', 'name': 'sample', 'skill_id': 'stable-id', 'content_sha256': result['content_sha256'], 'baseSkillHash': 'skill-hash', 'baseConfigHash': 'config-hash'}
            self.assertEqual(plan(root, commit, manifest, [binding])['changes'][0]['action'], 'noop')
            # Dirty filesystem cannot change a pinned source package.
            ref.write_text('Second reference', encoding='utf-8')
            self.assertEqual(plan(root, commit, manifest, [binding])['changes'][0]['action'], 'noop')
            git('add', 'skills')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.test', '-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'Reference update')
            new_commit = git('rev-parse', 'HEAD')
            update = plan(root, new_commit, manifest, [binding])['changes'][0]
            self.assertEqual(update['action'], 'update_draft')
            self.assertEqual(update['skill_id'], 'stable-id')
            self.assertNotEqual(update['content_sha256'], binding['content_sha256'])
            self.assertFalse(update['publish'])
            with self.assertRaises(ValueError):
                plan(root, commit, manifest, [binding, binding])
            ref.write_text('[Private](../../../projects/private.md)', encoding='utf-8')
            git('add', 'skills')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.test', '-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'Broken reference')
            blocked = plan(root, git('rev-parse', 'HEAD'), manifest, [binding])['changes'][0]
            self.assertEqual(blocked['action'], 'blocked')
