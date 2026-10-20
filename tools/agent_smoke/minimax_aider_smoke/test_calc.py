import unittest
from calc import total_with_tax


class TestTotalWithTax(unittest.TestCase):
    def test_twenty_percent(self):
        self.assertEqual(total_with_tax(1000, 20), 1200)

    def test_ten_percent(self):
        self.assertEqual(total_with_tax(250, 10), 275)

    def test_floor_partial_cent(self):
        self.assertEqual(total_with_tax(199, 5), 208)

    def test_zero_tax(self):
        self.assertEqual(total_with_tax(1000, 0), 1000)

    def test_negative_input(self):
        with self.assertRaises(ValueError):
            total_with_tax(-1, 10)


if __name__ == "__main__":
    unittest.main()
