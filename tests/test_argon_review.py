"""Offline regression tests. Never contacts KIE."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / 'tools' / 'ai_review' / 'argon_review.py'
spec = importlib.util.spec_from_file_location('argon_review', SRC)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def git(path, *args):
    return subprocess.run(['git','-C',str(path),*args],check=True,capture_output=True,encoding='utf-8')


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
        # The fake key is assembled at runtime on purpose: a contiguous
        # key-shaped literal in this file would trip the detector on the
        # tool's own diff, and the tool could never review this test file.
        fake_key = 'sk-' + 'abcdefghijklmno123456'
        self.change(f'key = "{fake_key}"\n')
        with self.assertRaises(review.ReviewError):
            review.snapshot(self.repo,'HEAD~1','HEAD')

    def test_split_key_literal_is_not_flagged(self):
        # A key-shaped literal split in the source is not a secret and must
        # not stop the review. The detector only fires on a contiguous match.
        self.change("key = 'sk-' + 'abcdefghijklmno123456'\n")
        files, diff, digest = review.snapshot(self.repo,'HEAD~1','HEAD')
        self.assertEqual(files,['code.py'])
        self.assertIn('abcdefghijklmno123456',diff)

    def test_empty_diff_never_calls(self):
        out=self.repo.parent/'empty-report.md'
        rc=review.main(['--repo',str(self.repo),'--base','HEAD','--head','HEAD','--scope','Check','--out',str(out),'--live'])
        self.assertEqual(rc,0)
        self.assertIn('EMPTY',out.read_text(encoding='utf-8'))

    def test_live_wrong_confirmation_does_not_call(self):
        self.change()
        with patch.dict('os.environ', {'KIE_API_KEY':'fake'}, clear=False):
            with patch('builtins.input',return_value='NOT REVIEW'), patch.object(review,'ask_argon', side_effect=AssertionError('network call')):
                rc=review.main(['--repo',str(self.repo),'--base','HEAD~1','--head','HEAD','--scope','Check','--out',str(self.repo.parent/'no-report.md'),'--live'])
        self.assertEqual(rc,2)

    def test_block_sensitive_file(self):
        (self.repo/'.env').write_text('HELLO=1\n',encoding='utf-8')
        git(self.repo,'add','.env')
        git(self.repo,'commit','-qm','add secret')
        with self.assertRaises(review.ReviewError):
            review.snapshot(self.repo,'HEAD~1','HEAD')

    def test_text_mentioning_binary_marker_is_allowed(self):
        # Regression: the binary check used to scan the diff text for the marker
        # string, so any diff that merely mentioned it was rejected as binary.
        # The tool's own source is such a diff, which blocked the review loop.
        self.change('note = "Binary files a and b differ"\n')
        files, diff, digest = review.snapshot(self.repo,'HEAD~1','HEAD')
        self.assertEqual(files,['code.py'])
        self.assertIn('Binary files a and b differ',diff)
        self.assertEqual(len(digest),64)

    def test_real_binary_file_is_rejected(self):
        (self.repo/'blob.bin').write_bytes(b'\x00\x01\x02\xff'*8)
        git(self.repo,'add','blob.bin')
        git(self.repo,'commit','-qm','add binary')
        with self.assertRaises(review.ReviewError):
            review.snapshot(self.repo,'HEAD~1','HEAD')

if __name__ == '__main__':
    unittest.main()