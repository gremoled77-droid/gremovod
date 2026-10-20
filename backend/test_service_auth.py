"""Список машинных токенов студии: несколько значений, зоны, обрезка пробелов.

Формат STUDIO_SERVICE_TOKENS=токен1:зона;токен2:зона. Пока в n8n-креде лежит не тот
секрет, стенд принимает дополнительные токены — их список собирает лаунчер стенда.
"""
import os
import unittest
from unittest import mock

from backend import service_auth


class ServiceAuthTokensTest(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop(service_auth.ENV, None)

    def tearDown(self):
        self.env.stop()

    def set_tokens(self, value):
        os.environ[service_auth.ENV] = value

    def test_single_token_with_zone(self):
        self.set_tokens('tok-a:*')
        self.assertEqual(service_auth.tokens(), {'tok-a': {'*'}})

    def test_two_tokens_have_independent_zones(self):
        self.set_tokens('tok-a:proj-1,proj-2;tok-b:*')
        self.assertEqual(
            service_auth.tokens(),
            {'tok-a': {'proj-1', 'proj-2'}, 'tok-b': {'*'}},
        )

    def test_surrounding_whitespace_is_trimmed(self):
        self.set_tokens(' tok-a : proj-1 ; tok-b : * ')
        self.assertEqual(
            service_auth.tokens(),
            {'tok-a': {'proj-1'}, 'tok-b': {'*'}},
        )

    def test_token_without_zone_is_not_issued(self):
        self.set_tokens('tok-a')
        self.assertEqual(service_auth.tokens(), {})

    def test_token_with_empty_zone_is_not_issued(self):
        self.set_tokens('tok-a:;tok-b:*')
        self.assertEqual(service_auth.tokens(), {'tok-b': {'*'}})

    def test_empty_entries_are_skipped(self):
        self.set_tokens(';;tok-a:*;;')
        self.assertEqual(service_auth.tokens(), {'tok-a': {'*'}})

    def test_token_with_colon_inside_value_is_split_on_first_colon(self):
        # Значение токена может содержать двоеточие: режем по первому, зона — остаток.
        self.set_tokens('to:ken:proj-1')
        self.assertEqual(service_auth.tokens(), {'to': {'ken:proj-1'}})


if __name__ == '__main__':
    unittest.main()
