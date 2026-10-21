"""Frozen owner regression for the relay smoke; no production Studio imports."""

import unittest

from value import nonnegative


class Regression(unittest.TestCase):
    def test_negative(self):
        self.assertEqual(nonnegative(-4), 0)

    def test_positive(self):
        self.assertEqual(nonnegative(7), 7)
