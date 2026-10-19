"""Offline regression tests. Never contacts KIE."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

# A normal import, not an importlib copy: argon_review and review_gate must
# share ONE module instance, otherwise the gate would use a different
# argon_review than the one these tests patch.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'ai_review'))
import argon_review as review  # noqa: E402
import review_gate  # noqa: E402


def git(path, *args):
    return subprocess.run(['git','-C',str(path),*args],check=True,capture_output=True,encoding='utf-8')


# Built at runtime on purpose: a credential-shaped literal written out in one
# piece would trip the secret guard on this repository's OWN diff, and the
# bridge could then never review the very code that implements it.
FAKE_SECRET = 'sk-' + 'abcdefghijklmno123456'


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git(self.repo,'init','-q')
        git(self.repo,'config','user.name','Test')
        git(self.repo,'config','user.email','test@example.org')
        (self.repo/'code.py').write_text('x = 1\n',encoding='utf-8')
        git(self.repo,'add','code.py')
        git(self.repo,'commit','-qm','base')

    def change(self, text='x = 2\n'):
        (self.repo/'code.py').write_text(text,encoding='utf-8')
        git(self.repo,'add','code.py')
        git(self.repo,'commit','-qm','change')

    def test_offline_and_repo_read_only(self):
        self.change()
        before = git(self.repo,'status','--porcelain').stdout
        out=self.repo.parent/'review-outside-repo.md'
        rc=review.main(['--repo',str(self.repo),'--base','HEAD~1','--head','HEAD','--scope','Check core','--out',str(out)])
        self.assertEqual(rc,0)
        self.assertIn('OFFLINE / PREVIEW',out.read_text(encoding='utf-8'))
        self.assertEqual(before,git(self.repo,'status','--porcelain').stdout)

    def test_secret_guard(self):
        self.change('key = "%s"\n' % FAKE_SECRET)
        with self.assertRaises(review.ReviewError):
            review.snapshot(self.repo,'HEAD~1','HEAD')

    def test_empty_diff_never_calls(self):
        out=self.repo.parent/'empty-report.md'
        with patch.object(review,'ask_argon_detailed',side_effect=AssertionError('network call')):
            rc=review.main(['--repo',str(self.repo),'--base','HEAD','--head','HEAD','--scope','Check','--out',str(out),'--live'])
        self.assertEqual(rc,0)
        self.assertIn('EMPTY',out.read_text(encoding='utf-8'))

    def test_live_wrong_confirmation_does_not_call(self):
        self.change()
        with patch.dict('os.environ', {'KIE_API_KEY':'fake'}, clear=False):
            with patch('builtins.input',return_value='NOT REVIEW'), \
                 patch.object(review,'ask_argon_detailed',side_effect=AssertionError('network call')), \
                 patch.object(review,'fetch_credits',side_effect=AssertionError('network call')):
                rc=review.main(['--repo',str(self.repo),'--base','HEAD~1','--head','HEAD','--scope','Check','--out',str(self.repo.parent/'no-report.md'),'--live'])
        self.assertEqual(rc,2)

    def test_live_without_an_approval_never_calls(self):
        """The standalone --live path spends only through the gate, and the
        gate refuses to spend without the owner's approval file."""
        self.change()
        _files,_diff,digest = review.snapshot(self.repo,'HEAD~1','HEAD')
        state = self.repo.parent/'state'
        with patch.dict('os.environ', {'KIE_API_KEY':'fake'}, clear=False):
            with patch('builtins.input',return_value='REVIEW %s' % digest[:12]), \
                 patch.object(review,'ask_argon_detailed',side_effect=AssertionError('network call')), \
                 patch.object(review,'fetch_credits',side_effect=AssertionError('network call')):
                rc=review.main(['--repo',str(self.repo),'--base','HEAD~1','--head','HEAD','--scope','Check','--out',str(self.repo.parent/'no-report2.md'),'--live','--state-dir',str(state)])
        self.assertEqual(rc,2)
        self.assertFalse((state/'ledger.json').exists())

    def test_block_sensitive_file(self):
        (self.repo/'.env').write_text('HELLO=1\n',encoding='utf-8')
        git(self.repo,'add','.env')
        git(self.repo,'commit','-qm','add secret')
        with self.assertRaises(review.ReviewError):
            review.snapshot(self.repo,'HEAD~1','HEAD')

if __name__ == '__main__':
    unittest.main()