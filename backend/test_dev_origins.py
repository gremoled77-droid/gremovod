import unittest

from backend.security import dev_origins


class DevOriginsTest(unittest.TestCase):
    def test_only_loopback_http_with_port(self):
        self.assertEqual(dev_origins('http://127.0.0.1:5273, http://localhost:5274'),
                         {'http://127.0.0.1:5273', 'http://localhost:5274'})

    def test_rejects_everything_else(self):
        for value in ['', 'https://127.0.0.1:5273', 'http://evil.test:5273', 'http://127.0.0.1',
                      'http://127.0.0.1:5273/x', 'http://user@127.0.0.1:5273', 'http://127.0.0.1:99999',
                      'http://192.168.1.5:5273', '*']:
            self.assertEqual(dev_origins(value), set(), value)


if __name__ == '__main__':
    unittest.main()
