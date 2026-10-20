"""Провайдеры генераций заменяемы; PiAPI — тестовый провайдер.

Проверки фиксируют решение: выбор провайдера принимает реестр, а не условие с
именем вендора в коде. Если провайдера начнут прибивать к PiAPI, тесты упадут.
"""
import asyncio
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend import main
from backend.model_catalog import LLM_MODELS, llm_spec, llm_resolve, llm_wire_model

BACKEND = Path(main.__file__).resolve().parent
# Условия, которыми провайдер раньше прибивался к PiAPI.
VENDOR_DECISIONS = (
    "provider!='piapi'",
    'provider != "piapi"',
    "provider not in {'piapi'",
    "body.provider!='piapi'",
    "body.provider != 'piapi'",
)


class RegistryProviderTests(unittest.TestCase):
    def test_every_model_declares_its_provider(self):
        for model, spec in LLM_MODELS.items():
            self.assertTrue(spec.get('provider'), f'{model}: провайдер не указан')
            self.assertIn(spec['provider'], main.PROVIDERS, f'{model}: провайдера нет в connections.PROVIDERS')

    def test_model_is_served_only_by_its_own_provider(self):
        self.assertIsNotNone(llm_spec('gpt-5.6-luna', 'piapi'))
        self.assertIsNone(llm_spec('gpt-5.6-luna', 'openai'))
        self.assertIsNone(llm_spec('нет-такой-модели', 'piapi'))

    def test_wire_name_and_registry_id_are_both_known(self):
        self.assertEqual(llm_wire_model('minimax-m3.1-flash'), 'MiniMax-M3.1-Flash')
        self.assertEqual(llm_resolve('MiniMax-M3.1-Flash')['provider'], 'piapi')
        self.assertEqual(llm_wire_model('gpt-5.6-luna'), 'gpt-5.6-luna')

    def test_provider_without_transport_is_refused(self):
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(main.provider_chat('провайдера-нет', 'key', {'model': 'm'}))
        self.assertEqual(caught.exception.status_code, 400)

    def test_key_of_another_provider_is_not_taken_from_request_header(self):
        """Ключ из заголовка принадлежит своему провайдеру, а не любому."""
        self.assertTrue(main.PROVIDERS['piapi'].get('header_key'))
        self.assertFalse(main.PROVIDERS.get('kie', {}).get('header_key'))
        with self.assertRaises(HTTPException):
            main.provider_credential('kie', 'piapi-ключ-из-заголовка')


class NoHardcodedVendorTests(unittest.TestCase):
    def test_llm_decisions_do_not_name_the_vendor(self):
        for name in ('main.py', 'llm_guard.py'):
            source = (BACKEND / name).read_text(encoding='utf-8')
            for fragment in VENDOR_DECISIONS:
                self.assertNotIn(fragment, source, f'{name}: провайдер прибит условием {fragment!r}')


if __name__ == '__main__':
    unittest.main()
