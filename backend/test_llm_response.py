import unittest

from fastapi import HTTPException

from backend.llm_response import chat_text
from backend.model_catalog import ALLOWED_CHAT


def reply(content, finish='stop', **extra):
    return {'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content, **extra}, 'finish_reason': finish}]}


class ChatTextTests(unittest.TestCase):
    def test_astra_is_allowed(self):
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


if __name__ == '__main__':
    unittest.main()
