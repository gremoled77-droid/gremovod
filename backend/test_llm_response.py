import unittest

from fastapi import HTTPException

from backend.llm_response import chat_text
from backend.model_catalog import ALLOWED_CHAT


def reply(content, finish='stop', **extra):
    return {'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content, **extra}, 'finish_reason': finish}]}


class ChatTextTests(unittest.TestCase):
    def test_astra_stays_for_prompt_writing(self):
        self.assertIn('gpt-5.6-luna', ALLOWED_CHAT)
        self.assertIn('gpt-6-astra', ALLOWED_CHAT)

    def test_plain_string(self):
        self.assertEqual(chat_text(reply(' Привет ')), 'Привет')

    def test_content_parts(self):
        parts = [{'type': 'text', 'text': 'Раз, '}, {'type': 'text', 'text': {'value': 'два'}}]
        self.assertEqual(chat_text(reply(parts)), 'Раз, два')

    def test_empty_answer_explains_finish_reason(self):
        with self.assertRaises(HTTPException) as caught:
            chat_text(reply('', finish='length'))
        self.assertIn('finish_reason: length', caught.exception.detail)
        self.assertIn('max_tokens', caught.exception.detail)

    def test_error_in_body_even_with_http_200(self):
        with self.assertRaises(HTTPException) as caught:
            chat_text({'code': 400, 'message': 'model not found'})
        self.assertIn('model not found', caught.exception.detail)
        with self.assertRaises(HTTPException) as caught:
            chat_text({'error': {'message': 'quota exceeded'}})
        self.assertIn('quota exceeded', caught.exception.detail)

    def test_missing_choices(self):
        with self.assertRaises(HTTPException):
            chat_text({'id': 'x', 'output': []})


class AuthHeaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_llm_uses_bearer_and_tasks_use_x_api_key(self):
        from unittest.mock import patch

        import httpx

        from backend import main

        seen = []

        async def fake(self, method, url, headers=None, json=None):
            seen.append((url, headers))
            return httpx.Response(200, json={'code': 200, 'data': {}, 'choices': [{'message': {'content': 'ok'}}]})

        with patch.object(httpx.AsyncClient, 'request', fake), patch.object(main, 'require_spend_reservation', lambda spend, payload=None: None):
            await main.request_piapi('POST', '/v1/chat/completions', 'secret-key', {'model': 'm'}, spend=('llm', 'req-1'))
            await main.request_piapi('GET', '/api/v1/task/1', 'secret-key')
        self.assertEqual(seen[0][1].get('Authorization'), 'Bearer secret-key')
        self.assertNotIn('X-API-KEY', seen[0][1])
        self.assertEqual(seen[1][1].get('X-API-KEY'), 'secret-key')
        self.assertNotIn('Authorization', seen[1][1])

if __name__ == '__main__':
    unittest.main()
