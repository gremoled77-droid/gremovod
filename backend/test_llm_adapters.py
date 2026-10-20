"""Тесты HTTP-адаптеров LLM-шлюза: три протокола, сбор usage, ошибки, ключи, реестр, гейт.

Сеть не используется: каждый провайдер закрыт httpx.MockTransport.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import HTTPException

from backend import connections
from backend import llm_adapters
from backend import llm_gateway

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CONFIG = ROOT / 'config' / 'llm_gateway.prices.example.json'

# Провайдер, модель, протокол, адрес и префикс пути — всё из реестра.
RATES = [
    {'provider': 'kie', 'model': 'gpt-6-luna', 'protocol': 'responses',
     'base_url': 'https://api.kie.ai', 'path_prefix': 'codex'},
    {'provider': 'kie', 'model': 'claude-haiku-5-5', 'protocol': 'anthropic_messages',
     'base_url': 'https://api.kie.ai', 'path_prefix': 'anthropic'},
    {'provider': 'piapi', 'model': 'gpt-5.6-luna', 'protocol': 'openai_chat',
     'base_url': 'https://api.piapi.ai', 'path_prefix': ''},
    {'provider': 'minimax', 'model': 'MiniMax-M3.1-Flash', 'protocol': 'openai_chat',
     'base_url': 'https://api.minimax.io', 'path_prefix': ''},
    {'provider': 'deepseek', 'model': 'deepseek-flash', 'protocol': 'openai_chat',
     'base_url': 'https://api.deepseek.com', 'path_prefix': ''},
    {'provider': 'openrouter', 'model': 'minimax/minimax-m3.1-flash:free', 'protocol': 'openai_chat',
     'base_url': 'https://openrouter.ai/api', 'path_prefix': ''},
]


def _config(disabled=(), unverified=(), prefixes=None, free=()):
    """Файл конфигурации шлюза с шестью маршрутами реестра."""
    prefixes = prefixes or {}
    rates = []
    for spec in RATES:
        provider, model = spec['provider'], spec['model']
        rate = {
            'provider': provider, 'model': model, 'model_id': model, 'role': 'extra',
            'input': 0.03, 'output': 0.15, 'cached_input_per_mtok': None,
            'source': 'https://example.test/' + model, 'as_of': '2026-10-20',
            'protocol': spec['protocol'], 'base_url': spec['base_url'],
            'path_prefix': prefixes.get((provider, model), spec['path_prefix']),
            'capabilities': {'tools': False, 'streaming': False, 'reasoning': False},
            'max_input_tokens': None, 'rate_limit': None, 'upstream_version': None,
            'free': provider in free, 'opt_in': provider in free,
            'promotion': False, 'quota_limited': False, 'requires_dynamic_tier_check': False,
            'enabled': provider not in disabled, 'verified_at': '2026-10-20',
        }
        if provider in unverified:
            rate['verified_at'] = None
        if provider in free:
            rate['input'] = 0
            rate['output'] = 0
        if provider in disabled:
            rate['enabled'] = False
            rate['verified_at'] = None
            rate['input'] = None
            rate['output'] = None
        rates.append(rate)
    return {
        'schema_version': 1, 'as_of': '2026-10-20', 'currency': 'USD',
        'unit': 'USD per 1000000 input or output tokens', 'status': 'test',
        'rates': rates,
        'comparison_display': {
            'card_primary': 'kie_piapi_reference_cost', 'budget_primary': 'confirmed_actual_provider_cost',
            'reference_provider_allowlist': ['kie', 'piapi'],
            'match_priority': 'exact_model_then_named_other_model_baseline',
            'default_baseline': {'provider': 'kie', 'model': 'gpt-6-luna', 'kind': 'reference_model'},
            'alternative_baseline': {'provider': 'piapi', 'model': 'gpt-5.6-luna', 'kind': 'reference_model'},
            'explicit_different_model_label_required': True, 'show_reference_snapshot_date': True,
            'free_api_actual_cost_usd': 0, 'paid_approval_must_show_actual_estimate': True,
            'unknown_charge_is_not_zero': True, 'pending_and_unknown_reported_separately': True,
            'small_amount_precision': 6,
        },
    }


class AdapterCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='llm-adapters-')
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.counter = 0
        # основной тестовый реестр: маршрут deepseek выключен владельцем
        self.registry = self.write_registry(_config(disabled=('deepseek',)))
        # тот же реестр, но со всеми включёнными маршрутами
        self.enabled_registry = self.write_registry(_config(free=('openrouter',)))
        self.messages = [{'role': 'system', 'content': 'Правила студии.'},
                         {'role': 'user', 'content': 'Собери бриф.'}]

    def write_registry(self, payload):
        self.counter += 1
        path = Path(self.tmp) / ('llm_gateway.%d.json' % self.counter)
        path.write_text(json.dumps(payload), encoding='utf-8')
        return llm_gateway.load_registry(str(path))

    def route(self, provider, model, registry=None):
        entry = (registry or self.enabled_registry).entry(provider, model)
        self.assertIsNotNone(entry, provider + '/' + model)
        return entry.route()

    def client(self, handler):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        self.addCleanup(client.aclose)
        return client


class ProtocolTests(AdapterCase):
    async def test_responses_protocol_returns_text_and_usage(self):
        """Kie GPT-6 Luna: ответы-протокол, текст из output, usage с кешем и размышлением."""
        seen = {}

        def handler(request):
            seen['url'] = str(request.url)
            seen['body'] = json.loads(request.content)
            seen['auth'] = request.headers.get('authorization')
            return httpx.Response(200, json={
                'id': 'resp_2026_01',
                'output': [{'type': 'message',
                            'content': [{'type': 'output_text', 'text': 'Бриф готов.'}]}],
                'usage': {'input_tokens': 5000, 'output_tokens': 1000,
                          'input_tokens_details': {'cached_tokens': 400},
                          'output_tokens_details': {'reasoning_tokens': 250}},
            }, request=request)

        result = await llm_adapters.complete(self.route('kie', 'gpt-6-luna'), self.messages, 512,
                                             client=self.client(handler), api_key='test-key',
                                             registry=self.enabled_registry)
        self.assertTrue(result.ok, result.error_kind)
        self.assertEqual(result.text, 'Бриф готов.')
        self.assertIsNone(result.error_kind)
        self.assertFalse(result.charged_possible)
        self.assertEqual(result.provider_request_id, 'resp_2026_01')
        self.assertEqual(result.usage.input_tokens, 5000)
        self.assertEqual(result.usage.output_tokens, 1000)
        self.assertEqual(result.usage.cached_input_tokens, 400)
        self.assertEqual(result.usage.reasoning_tokens, 250)
        self.assertFalse(result.usage.estimated)
        # адрес из документации провайдера: https://api.kie.ai/codex/v1/responses
        self.assertEqual(seen['url'], 'https://api.kie.ai/codex/v1/responses')
        self.assertEqual(seen['body']['model'], 'gpt-6-luna')
        self.assertEqual(seen['body']['max_output_tokens'], 512)
        self.assertEqual(seen['auth'], 'Bearer test-key')

    async def test_path_prefix_is_taken_from_registry_not_from_code(self):
        """Префикс пути — строка конфигурации: сменили в реестре — сменился адрес."""
        seen = {}

        def handler(request):
            seen['url'] = str(request.url)
            return httpx.Response(200, json={
                'id': 'resp_1', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Ок.'}]}],
                'usage': {'input_tokens': 5, 'output_tokens': 2},
            }, request=request)

        registry = self.write_registry(_config(prefixes={('kie', 'gpt-6-luna'): 'api'}))
        result = await llm_adapters.complete(self.route('kie', 'gpt-6-luna', registry), self.messages, 64,
                                             client=self.client(handler), api_key='test-key', registry=registry)
        self.assertTrue(result.ok, result.error_kind)
        self.assertEqual(seen['url'], 'https://api.kie.ai/api/v1/responses')

    async def test_anthropic_messages_protocol_uses_its_own_body(self):
        """Kie Claude Haiku: сообщения Anthropic — system отдельно, роли только user/assistant."""
        seen = {}

        def handler(request):
            seen['url'] = str(request.url)
            seen['body'] = json.loads(request.content)
            seen['api_key'] = request.headers.get('x-api-key')
            seen['version'] = request.headers.get('anthropic-version')
            return httpx.Response(200, json={
                'id': 'msg_2026_01', 'type': 'message', 'role': 'assistant',
                'content': [{'type': 'text', 'text': 'Черновик готов.'}],
                # input_tokens у Anthropic не включает кеш: всего входа 100+30
                'usage': {'input_tokens': 100, 'output_tokens': 20, 'cache_read_input_tokens': 30},
            }, request=request)

        result = await llm_adapters.complete(self.route('kie', 'claude-haiku-5-5'), self.messages, 300,
                                             client=self.client(handler), api_key='test-key',
                                             registry=self.enabled_registry)
        self.assertTrue(result.ok, result.error_kind)
        self.assertEqual(result.text, 'Черновик готов.')
        self.assertEqual(result.provider_request_id, 'msg_2026_01')
        self.assertEqual(result.usage.input_tokens, 130)
        self.assertEqual(result.usage.output_tokens, 20)
        self.assertEqual(result.usage.cached_input_tokens, 30)
        self.assertIsNone(result.usage.reasoning_tokens)
        # адрес из документации провайдера: https://api.kie.ai/anthropic/v1/messages
        self.assertEqual(seen['url'], 'https://api.kie.ai/anthropic/v1/messages')
        self.assertEqual(seen['body']['model'], 'claude-haiku-5-5')
        self.assertEqual(seen['body']['max_tokens'], 300)
        self.assertEqual(seen['body']['system'], 'Правила студии.')
        self.assertEqual(seen['body']['messages'], [{'role': 'user', 'content': 'Собери бриф.'}])
        self.assertEqual(seen['api_key'], 'test-key')
        self.assertEqual(seen['version'], '2023-06-01')

    async def test_anthropic_cache_write_tokens_are_not_lost(self):
        """Запись в кеш — тоже вход: 100 + 30 прочитанных + 12 записанных."""
        def handler(request):
            return httpx.Response(200, json={
                'id': 'msg_1', 'role': 'assistant',
                'content': [{'type': 'text', 'text': 'Готово.'}],
                'usage': {'input_tokens': 100, 'output_tokens': 20,
                          'cache_read_input_tokens': 30, 'cache_creation_input_tokens': 12},
            }, request=request)

        result = await llm_adapters.complete(self.route('kie', 'claude-haiku-5-5'), self.messages, 64,
                                             client=self.client(handler), api_key='test-key',
                                             registry=self.enabled_registry)
        self.assertTrue(result.ok, result.error_kind)
        self.assertEqual(result.usage.input_tokens, 142)
        self.assertEqual(result.usage.cached_input_tokens, 30)

    async def test_openai_chat_protocol_for_every_chat_provider(self):
        """Чат-протокол: PiAPI, MiniMax, DeepSeek, OpenRouter."""
        cases = [
            ('piapi', 'gpt-5.6-luna', 'https://api.piapi.ai/v1/chat/completions'),
            ('minimax', 'MiniMax-M3.1-Flash', 'https://api.minimax.io/v1/chat/completions'),
            ('deepseek', 'deepseek-flash', 'https://api.deepseek.com/v1/chat/completions'),
            ('openrouter', 'minimax/minimax-m3.1-flash:free', 'https://openrouter.ai/api/v1/chat/completions'),
        ]
        for provider, model, expected_url in cases:
            with self.subTest(provider=provider):
                seen = {}

                def handler(request):
                    seen['url'] = str(request.url)
                    seen['body'] = json.loads(request.content)
                    return httpx.Response(200, json={
                        'id': 'chatcmpl-777',
                        'choices': [{'message': {'role': 'assistant', 'content': 'Есть.'}}],
                        'usage': {'prompt_tokens': 120, 'completion_tokens': 45,
                                  'prompt_tokens_details': {'cached_tokens': 20},
                                  'completion_tokens_details': {'reasoning_tokens': 7}},
                    }, request=request)

                result = await llm_adapters.complete(self.route(provider, model), self.messages, 256,
                                                     client=self.client(handler), api_key='test-key',
                                                     registry=self.enabled_registry, allow_free=True)
                self.assertTrue(result.ok, result.error_kind)
                self.assertEqual(result.text, 'Есть.')
                self.assertEqual(result.provider_request_id, 'chatcmpl-777')
                self.assertEqual(result.usage.input_tokens, 120)
                self.assertEqual(result.usage.output_tokens, 45)
                self.assertEqual(result.usage.cached_input_tokens, 20)
                self.assertEqual(result.usage.reasoning_tokens, 7)
                self.assertEqual(seen['url'], expected_url)
                self.assertEqual(seen['body']['model'], model)
                self.assertEqual(seen['body']['max_tokens'], 256)
                self.assertEqual(seen['body']['messages'], self.messages)


class ErrorTests(AdapterCase):
    async def test_error_kinds_are_distinguished(self):
        """Каждый вид отказа провайдера опознаётся отдельно; списание не обнуляется молча."""
        cases = [
            # 401: ключ отклонён — запрос не обработан, списания не было
            ('http_401', httpx.Response(401, json={'error': {'message': 'invalid api key'}}), False),
            # 403: доступ закрыт после отправки — списание неизвестно
            ('http_403', httpx.Response(403, json={'error': {'message': 'forbidden'}}), True),
            # блокировка Cloudflare
            ('cloudflare_1010', httpx.Response(403, text='browser_signature_banned Error 1010'), True),
            ('http_429', httpx.Response(429, json={'error': {'message': 'rate limit reached'}}), True),
            ('http_5xx', httpx.Response(503, text='upstream unavailable'), True),
            # HTTP 200 с телом-ошибкой: провайдер отказал, обработки не было
            ('bad_body', httpx.Response(200, json={'code': 500, 'msg': 'internal error'}), False),
            # HTTP 200 без распознаваемого ответа: неизвестно, обработал ли провайдер запрос
            ('bad_body', httpx.Response(200, json={'id': 'chatcmpl-1',
                                                  'usage': {'prompt_tokens': 10, 'completion_tokens': 2}}), True),
        ]
        for kind, response, charged in cases:
            with self.subTest(kind=kind, status=response.status_code):
                def handler(request, response=response):
                    return response

                result = await llm_adapters.complete(self.route('piapi', 'gpt-5.6-luna'), self.messages, 64,
                                                     client=self.client(handler), api_key='test-key',
                                                     registry=self.enabled_registry)
                self.assertFalse(result.ok)
                self.assertEqual(result.error_kind, kind)
                self.assertEqual(result.charged_possible, charged)
                self.assertEqual(result.text, '')
                self.assertIsNone(result.usage.input_tokens)
                self.assertIsNone(result.usage.output_tokens)

    async def test_timeout_is_unknown_charge_not_free(self):
        """Таймаут: ответа нет, но списание могло произойти."""
        def handler(request):
            raise httpx.ReadTimeout('timed out', request=request)

        result = await llm_adapters.complete(self.route('piapi', 'gpt-5.6-luna'), self.messages, 64,
                                             client=self.client(handler), api_key='test-key',
                                             registry=self.enabled_registry)
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, 'timeout')
        self.assertTrue(result.charged_possible)
        self.assertEqual(result.text, '')

    async def test_response_without_usage_is_not_free(self):
        """Успешный ответ без расхода токенов — неизвестное списание, а не «бесплатно»."""
        def handler(request):
            return httpx.Response(200, json={'id': 'chatcmpl-1', 'choices': [
                {'message': {'role': 'assistant', 'content': 'Есть.'}}]})

        result = await llm_adapters.complete(self.route('piapi', 'gpt-5.6-luna'), self.messages, 64,
                                             client=self.client(handler), api_key='test-key',
                                             registry=self.enabled_registry)
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, 'no_usage')
        self.assertTrue(result.charged_possible)
        self.assertIsNone(result.usage.input_tokens)
        self.assertIsNone(result.usage.output_tokens)
        self.assertTrue(result.usage.estimated)

    async def test_error_result_keeps_key_and_upstream_body_out(self):
        """Ключ и тело провайдера в результате не появляются."""
        def handler(request):
            return httpx.Response(500, text='private-key-abc123 upstream internals')

        result = await llm_adapters.complete(self.route('piapi', 'gpt-5.6-luna'), self.messages, 64,
                                             client=self.client(handler), api_key='test-key',
                                             registry=self.enabled_registry)
        self.assertEqual(result.error_kind, 'http_5xx')
        self.assertNotIn('private-key-abc123', result.text)
        self.assertNotIn('upstream internals', result.text)
        self.assertNotIn('test-key', result.text)


class RegistryTrustTests(AdapterCase):
    async def test_address_and_model_are_taken_only_from_registry(self):
        """Подсунутый пользователем адрес и модель сетевого вызова не вызывают."""
        seen = {}

        def handler(request):
            seen['url'] = str(request.url)
            seen['body'] = json.loads(request.content)
            return httpx.Response(200, json={
                'id': 'resp_1', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Ок.'}]}],
                'usage': {'input_tokens': 5, 'output_tokens': 2},
            }, request=request)

        hostile = llm_gateway.Route(provider='kie', model='gpt-6-luna', model_id='gpt-6-luna', protocol='responses',
                                    role='simple', base_url='https://evil.example', free=False, opt_in=False)
        messages = [{'role': 'user', 'content': 'Привет', 'model': 'evil-model', 'base_url': 'https://evil.example'}]
        result = await llm_adapters.complete(hostile, messages, 64, client=self.client(handler),
                                             api_key='test-key', registry=self.enabled_registry)
        self.assertTrue(result.ok, result.error_kind)
        self.assertEqual(seen['url'], 'https://api.kie.ai/codex/v1/responses')
        self.assertEqual(seen['body']['model'], 'gpt-6-luna')
        self.assertNotIn('evil-model', json.dumps(seen['body']))
        self.assertNotIn('evil.example', json.dumps(seen['body']))

    async def test_provider_outside_registry_makes_no_network_call(self):
        """Провайдер, которого нет в реестре, сетевого вызова не вызывает."""
        def handler(request):
            raise AssertionError('сетевой вызов не должен состояться')

        hostile = llm_gateway.Route(provider='evil', model='evil-model', model_id='evil-model', protocol='responses',
                                    role='simple', base_url='https://evil.example', free=False, opt_in=False)
        with self.assertRaises(HTTPException):
            await llm_adapters.complete(hostile, self.messages, 64, client=self.client(handler),
                                        api_key='test-key', registry=self.enabled_registry)

    async def test_key_is_read_from_connections_environment(self):
        """Ключ берётся по схеме проекта: переменная окружения, значение не попадает в результат."""
        seen = {}

        def handler(request):
            seen['auth'] = request.headers.get('authorization')
            return httpx.Response(200, json={
                'id': 'chatcmpl-9', 'choices': [{'message': {'role': 'assistant', 'content': 'Есть.'}}],
                'usage': {'prompt_tokens': 3, 'completion_tokens': 1},
            }, request=request)

        with patch.dict(os.environ, {'PIAPI_API_KEY': 'env-secret-key'}):
            result = await llm_adapters.complete(self.route('piapi', 'gpt-5.6-luna'), self.messages, 64,
                                                 client=self.client(handler), registry=self.enabled_registry)
        self.assertTrue(result.ok, result.error_kind)
        self.assertEqual(seen['auth'], 'Bearer env-secret-key')
        self.assertNotIn('env-secret-key', result.text)

    async def test_missing_key_makes_no_network_call(self):
        """Без настроенного ключа сеть не трогается: провайдеру нечего предъявлять."""
        def handler(request):
            raise AssertionError('сетевой вызов не должен состояться')

        with patch.dict(os.environ, {'PIAPI_API_KEY': ''}), patch.object(connections, 'ROOT', Path(self.tmp)):
            with self.assertRaises(HTTPException):
                await llm_adapters.complete(self.route('piapi', 'gpt-5.6-luna'), self.messages, 64,
                                            client=self.client(handler), registry=self.enabled_registry)


class OwnerGateTests(AdapterCase):
    """Гейт владельца: маршрут, который не включён и не подтверждён, сеть не трогает."""

    def counting_handler(self, calls):
        def handler(request):
            calls.append(request)
            return httpx.Response(200, json={
                'id': 'chatcmpl-1', 'choices': [{'message': {'role': 'assistant', 'content': 'Есть.'}}],
                'usage': {'prompt_tokens': 3, 'completion_tokens': 1},
            }, request=request)
        return handler

    async def test_disabled_route_makes_no_network_call(self):
        """Маршрут с enabled=false в реестре сетевого вызова не даёт."""
        calls = []
        route = self.route('deepseek', 'deepseek-flash', self.registry)
        with self.assertRaises(HTTPException):
            await llm_adapters.complete(route, self.messages, 64, client=self.client(self.counting_handler(calls)),
                                        api_key='test-key', registry=self.registry)
        self.assertEqual(calls, [])

    async def test_opt_in_route_without_permission_makes_no_network_call(self):
        """Маршрут по оптину без явного разрешения — отказ."""
        calls = []
        route = self.route('openrouter', 'minimax/minimax-m3.1-flash:free', self.enabled_registry)
        with self.assertRaises(HTTPException):
            await llm_adapters.complete(route, self.messages, 64, client=self.client(self.counting_handler(calls)),
                                        api_key='test-key', registry=self.enabled_registry)
        self.assertEqual(calls, [])

    async def test_free_route_with_zero_tariff_is_allowed(self):
        """Подтверждённо бесплатный маршрут (тариф 0/0) проходит без verified_at."""
        calls = []
        route = self.route('openrouter', 'minimax/minimax-m3.1-flash:free', self.enabled_registry)
        result = await llm_adapters.complete(route, self.messages, 64,
                                             client=self.client(self.counting_handler(calls)),
                                             api_key='test-key', registry=self.enabled_registry, allow_free=True)
        self.assertTrue(result.ok, result.error_kind)
        self.assertEqual(len(calls), 1)

    async def test_unverified_paid_route_makes_no_network_call(self):
        """Платный маршрут без подтверждения тарифа (verified_at=null) — отказ."""
        calls = []
        registry = self.write_registry(_config(unverified=('kie',)))
        route = self.route('kie', 'gpt-6-luna', registry)
        with self.assertRaises(HTTPException):
            await llm_adapters.complete(route, self.messages, 64, client=self.client(self.counting_handler(calls)),
                                        api_key='test-key', registry=registry)
        self.assertEqual(calls, [])

    async def test_default_registry_is_closed(self):
        """Без явного реестра берётся приложенный пример — там всё выключено, сети нет."""
        calls = []
        example = llm_gateway.load_registry(str(EXAMPLE_CONFIG))
        route = example.entry('kie', 'gpt-6-luna').route()
        with patch.object(llm_gateway, 'load_registry', lambda path=None: example):
            with self.assertRaises(HTTPException):
                await llm_adapters.complete(route, self.messages, 64,
                                            client=self.client(self.counting_handler(calls)), api_key='test-key')
        self.assertEqual(calls, [])

    async def test_adapter_usage_feeds_registry_tariff_as_micro_sum(self):
        """Микросумма: usage из адаптера и тариф реестра дают $0.000300, а не $0."""
        def handler(request):
            return httpx.Response(200, json={
                'id': 'resp_1', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Ок.'}]}],
                'usage': {'input_tokens': 5000, 'output_tokens': 1000},
            }, request=request)

        route = self.route('kie', 'gpt-6-luna')
        result = await llm_adapters.complete(route, self.messages, 64, client=self.client(handler),
                                             api_key='test-key', registry=self.enabled_registry)
        self.assertTrue(result.ok, result.error_kind)
        quote = llm_gateway.actual_quote(self.enabled_registry, route, result.usage)
        self.assertEqual(quote.status, 'confirmed')
        self.assertEqual(quote.cost_usd, 0.0003)
        self.assertNotEqual(quote.cost_usd, 0)


class ConnectionsTests(unittest.TestCase):
    def test_new_providers_follow_existing_key_scheme(self):
        for provider, env, file in (('minimax', 'MINIMAX_API_KEY', 'MINIMAX_API_KEY.txt'),
                                    ('deepseek', 'DEEPSEEK_API_KEY', 'DEEPSEEK_API_KEY.txt'),
                                    ('openrouter', 'OPENROUTER_API_KEY', 'OPENROUTER_API_KEY.txt')):
            spec = connections.PROVIDERS[provider]
            self.assertEqual(spec['env'], env)
            self.assertEqual(spec['file'], file)
            self.assertTrue(spec['url'].startswith('https://'), provider)
            self.assertTrue(spec['docs'].startswith('https://'), provider)

    def test_credential_priority_is_header_then_env_then_file(self):
        with patch.dict(os.environ, {'MINIMAX_API_KEY': 'env-key'}):
            key, source = connections.credential('minimax', header='header-key')
            self.assertEqual(key, 'header-key')
            self.assertEqual(source, 'заголовок запроса')
            key, source = connections.credential('minimax')
            self.assertEqual(key, 'env-key')
            self.assertEqual(source, 'переменная окружения')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'DEEPSEEK_API_KEY.txt'
            path.write_text('file-key\n', encoding='utf-8')
            with patch.dict(os.environ, {'DEEPSEEK_API_KEY': ''}):
                key, source = connections.credential('deepseek', file_override=path)
            self.assertEqual(key, 'file-key')
            self.assertEqual(source, 'файл проекта')

    def test_connection_info_reports_configured_without_exposing_key(self):
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'super-secret-key'}):
            info = connections.connection_info('openrouter')
        self.assertTrue(info['configured'])
        self.assertEqual(info['source'], 'переменная окружения')
        self.assertNotIn('super-secret-key', json.dumps(info, ensure_ascii=False))
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': ''}), patch.object(connections, 'ROOT', Path(tmp)):
                info = connections.connection_info('openrouter')
            self.assertFalse(info['configured'])
            self.assertEqual(info['status'], 'not_configured')

    def test_env_example_lists_new_keys_with_empty_values(self):
        text = (ROOT / '.env.example').read_text(encoding='utf-8')
        for name in ('MINIMAX_API_KEY', 'DEEPSEEK_API_KEY', 'OPENROUTER_API_KEY'):
            lines = [line for line in text.splitlines() if line.startswith(name + '=')]
            self.assertEqual(len(lines), 1, name)
            self.assertEqual(lines[0], name + '=', name)


if __name__ == '__main__':
    unittest.main()
