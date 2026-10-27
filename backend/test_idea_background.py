import unittest
from unittest.mock import patch
from backend import idea_background, llm_guard, main, test_smoke


class IdeaBackgroundTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def test_digest_file_is_short_and_covers_the_sources(self):
        value = idea_background.load()
        self.assertTrue(value['text'].startswith('Сценарный фон'))
        self.assertTrue(1500 < value['chars'] < 4500, value['chars'])
        for needle in ('Изменение вместо активности', 'Бит', 'Юмор', 'Формат ответа', 'Проверка:'):
            self.assertIn(needle, value['text'])
        self.assertEqual(len(value['version']), 12)

    def test_endpoint_serves_the_digest(self):
        data = self.client.get('/api/idea/background').json()
        self.assertEqual(data['text'], idea_background.load()['text'])
        self.assertEqual(data['chars'], len(data['text']))
        self.assertEqual(len(data['topics']), 6)

    def test_missing_file_gives_empty_digest(self):
        with patch.object(idea_background, 'PATH', idea_background.PATH.with_name('nope.md')):
            value = idea_background.load()
        self.assertEqual((value['text'], value['chars']), ('', 0))

    def test_digest_fits_the_llm_input_limit_with_a_long_brief(self):
        brief = 'я' * 6000
        messages = [{'role': 'system', 'content': 'x' * 400 + idea_background.load()['text']}, {'role': 'user', 'content': brief}]
        self.assertLess(sum(len(m['content']) for m in messages), llm_guard.MAX_INPUT_CHARS)
        self.assertLess(llm_guard.estimate_usd('gpt-6-astra', messages, 2000), 0.05)


if __name__ == '__main__':
    unittest.main()
