"""Вывод внешних медиа-команд читается как UTF-8 независимо от кодировки Windows."""
import sys
import unittest

from tools import mock_media_pilot


class InvokeEncodingTests(unittest.TestCase):
    def test_cyrillic_utf8_output_is_read(self):
        # «И» в UTF-8 содержит байт 0x98, которого нет в cp1251: раньше stdout становился None.
        out = mock_media_pilot.invoke([sys.executable, '-c', "import sys; sys.stdout.buffer.write('03_Монтаж/И.mp4'.encode('utf-8'))"])
        self.assertEqual(out, '03_Монтаж/И.mp4')


if __name__ == '__main__':
    unittest.main()
