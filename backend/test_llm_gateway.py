"""Тесты ядра LLM-шлюза: реестр, тарифный ориентир, фактическое списание, выбор маршрута."""
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend import llm_gateway

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = ROOT / 'config' / 'llm_gateway.prices.example.json'
REQUIRED_RATE_FIELDS = ('provider', 'model', 'model_id', 'role', 'free', 'opt_in', 'input', 'output',
                        'source', 'as_of', 'protocol', 'enabled', 'verified_at', 'capabilities',
                        'max_input_tokens', 'cached_input_per_mtok', 'rate_limit', 'upstream_version')


def rate(provider, model, **over):
    """Запись реестра с полным набором полей схемы."""
    item = {
        'provider': provider, 'model': model, 'model_id': model, 'role': 'extra',
        'input': None, 'output': None, 'cached_input_per_mtok': None,
        'source': 'https://example.test/' + model, 'as_of': '2026-10-20', 'protocol': 'openai_chat',
        'base_url': 'https://example.test', 'capabilities': {'tools': False, 'streaming': False, 'reasoning': False},
        'max_input_tokens': None, 'rate_limit': None, 'upstream_version': None,
        'free': False, 'opt_in': False, 'promotion': False, 'quota_limited': False,
        'requires_dynamic_tier_check': False, 'enabled': True, 'verified_at': '2026-10-20',
    }
    item.update(over)
    return item


def config(*rates):
    """Файл конфигурации шлюза с базовой линией ориентира по умолчанию."""
    return {
        'schema_version': 1, 'as_of': '2026-10-20', 'currency': 'USD',
        'unit': 'USD per 1000000 input or output tokens', 'status': 'test',
        'rates': list(rates),
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
        'sample_limits_only': {'per_call_usd': 0.1, 'per_day_usd': 1, 'per_month_usd': 10,
                               'do_not_override_existing_owner_limits': True},
    }


def standard_config():
    return config(
        rate('kie', 'gpt-6-luna', role='simple', input=0.03, output=0.15, protocol='responses'),
        rate('kie', 'claude-haiku-5-5', role='editorial', input=0.06, output=0.3, protocol='anthropic_messages'),
        rate('piapi', 'gpt-5.6-luna', role='extra', input=0.02, output=0.12),
        rate('minimax', 'MiniMax-M3.1-Flash', role='coding', input=0.15, output=0.6),
        rate('deepseek', 'deepseek-flash', role='backup', input=None, output=None, requires_dynamic_tier_check=True),
        rate('openrouter', 'minimax/minimax-m3.1-flash:free', role='coding', input=0, output=0,
             free=True, opt_in=True, quota_limited=True),
    )


class RegistryCase(unittest.TestCase):
    def write_registry(self, payload):
        tmp = tempfile.mkdtemp(prefix='llm-gateway-')
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        path = Path(tmp) / 'llm_gateway.prices.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        return llm_gateway.load_registry(str(path))


class RegistryTests(RegistryCase):
    def test_missing_config_file_falls_back_to_example_with_disabled_routes(self):
        registry = llm_gateway.load_registry(str(ROOT / 'config' / 'llm_gateway.absent.json'))
        self.assertEqual(registry.source_path, str(EXAMPLE_PATH))
        self.assertEqual(len(registry.entries), 6)
        self.assertTrue(registry.routes)
        self.assertFalse([route for route in registry.routes if route.enabled])

    def test_example_config_has_full_schema_and_parses_without_errors(self):
        payload = json.loads(EXAMPLE_PATH.read_text(encoding='utf-8'))
        for item in payload['rates']:
            for field in REQUIRED_RATE_FIELDS:
                self.assertIn(field, item, (item.get('model'), field))
        registry = llm_gateway.load_registry(str(EXAMPLE_PATH))
        self.assertEqual(len(registry.entries), 6)
        kie = registry.entry('kie', 'gpt-6-luna')
        self.assertIsNotNone(kie)
        self.assertEqual(kie.role, 'simple')
        self.assertEqual(kie.model_id, 'gpt-6-luna')
        self.assertFalse(kie.free)
        self.assertFalse(kie.opt_in)
        self.assertFalse(kie.enabled)
        self.assertIsNone(kie.verified_at)
        self.assertEqual(kie.capabilities.tools, False)
        self.assertEqual(kie.input_per_mtok, 0.03)
        self.assertEqual(kie.output_per_mtok, 0.15)
        self.assertEqual(kie.source, 'https://kie.ai/gpt-6-sol-and-luna')

    def test_example_config_keeps_no_secrets(self):
        text = EXAMPLE_PATH.read_text(encoding='utf-8').lower()
        self.assertNotIn('api_key', text)
        self.assertNotIn('apikey', text)
        self.assertNotIn('secret', text)
        self.assertNotIn('bearer', text)

    def test_real_config_file_name_is_ignored_by_git(self):
        # .gitignore в проекте сохранён в cp1251, поэтому читаем побайтно
        raw = (ROOT / '.gitignore').read_bytes().decode('utf-8', errors='replace')
        lines = [line.strip() for line in raw.splitlines()]
        ignored = [line for line in lines if 'llm_gateway.prices.json' in line]
        self.assertTrue(ignored, 'реальный конфиг шлюза должен быть в .gitignore')
        self.assertFalse([line for line in ignored if 'example' in line])


class ReferenceQuoteTests(RegistryCase):
    """Тарифный ориентир: сколько вызов стоил бы по тарифу Kie.ai/PiAPI."""

    def test_model_sold_by_kie_is_compared_with_its_exact_tariff(self):
        registry = self.write_registry(standard_config())
        route = registry.route('kie', 'gpt-6-luna')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(5000, 1000))
        self.assertEqual(quote.kind, 'exact_model')
        self.assertEqual(quote.provider, 'kie')
        self.assertEqual(quote.model, 'gpt-6-luna')
        self.assertEqual(quote.rate_source, 'https://example.test/gpt-6-luna')
        self.assertEqual(quote.rate_as_of, '2026-10-20')
        self.assertTrue(quote.rate_verified)
        self.assertIn('Kie.ai', quote.label)

    def test_reference_cost_for_5000_input_1000_output_is_0_000300(self):
        registry = self.write_registry(standard_config())
        route = registry.route('kie', 'gpt-6-luna')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(5000, 1000))
        # (5000 * 0.03 + 1000 * 0.15) / 1000000 = 0.000300 — из документа о правиле показа цены
        self.assertEqual(round(quote.cost_usd, 6), 0.000300)
        self.assertIn('0.000300', quote.label)

    def test_free_route_gets_named_baseline_and_is_marked_as_other_model(self):
        registry = self.write_registry(standard_config())
        route = registry.route('openrouter', 'minimax/minimax-m3.1-flash:free')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(5000, 1000))
        self.assertEqual(quote.kind, 'reference_model')
        self.assertEqual(quote.provider, 'kie')
        self.assertEqual(quote.model, 'gpt-6-luna')
        self.assertEqual(round(quote.cost_usd, 6), 0.000300)
        self.assertIn('другая модель', quote.label)
        self.assertIn('сравнение по объёму токенов', quote.label)

    def test_baseline_is_taken_from_config_not_hardcoded(self):
        payload = standard_config()
        payload['comparison_display']['default_baseline'] = {'provider': 'piapi', 'model': 'gpt-5.6-luna',
                                                             'kind': 'reference_model'}
        registry = self.write_registry(payload)
        route = registry.route('openrouter', 'minimax/minimax-m3.1-flash:free')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(5000, 1000))
        self.assertEqual(quote.kind, 'reference_model')
        self.assertEqual(quote.provider, 'piapi')
        self.assertEqual(quote.model, 'gpt-5.6-luna')
        # (5000 * 0.02 + 1000 * 0.12) / 1000000 = 0.000220
        self.assertEqual(round(quote.cost_usd, 6), 0.000220)

    def test_alternative_baseline_is_used_when_default_baseline_is_missing(self):
        payload = config(
            rate('piapi', 'gpt-5.6-luna', role='extra', input=0.02, output=0.12),
            rate('openrouter', 'minimax/minimax-m3.1-flash:free', role='coding', input=0, output=0,
                 free=True, opt_in=True),
        )
        registry = self.write_registry(payload)
        route = registry.route('openrouter', 'minimax/minimax-m3.1-flash:free')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(5000, 1000))
        self.assertEqual(quote.kind, 'reference_model')
        self.assertEqual(quote.provider, 'piapi')
        self.assertEqual(quote.model, 'gpt-5.6-luna')
        self.assertEqual(round(quote.cost_usd, 6), 0.000220)

    def test_missing_tariff_is_unavailable_without_a_zero(self):
        payload = config(rate('openrouter', 'minimax/minimax-m3.1-flash:free', free=True, opt_in=True,
                              input=0, output=0))
        registry = self.write_registry(payload)
        route = registry.route('openrouter', 'minimax/minimax-m3.1-flash:free')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(5000, 1000))
        self.assertEqual(quote.kind, 'unavailable')
        self.assertEqual(quote.status, 'unavailable')
        self.assertIsNone(quote.cost_usd)
        self.assertNotIn('$0', quote.label)
        self.assertIn('Тариф не подтверждён', quote.label)

    def test_exact_model_record_without_tariff_is_unavailable_and_does_not_crash(self):
        payload = standard_config()
        payload['rates'][0]['input'] = None
        payload['rates'][0]['output'] = None
        registry = self.write_registry(payload)
        route = registry.route('kie', 'gpt-6-luna')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(5000, 1000))
        self.assertEqual(quote.kind, 'unavailable')
        self.assertEqual(quote.status, 'unavailable')
        self.assertIsNone(quote.cost_usd)
        self.assertNotIn('$0', quote.label)
        self.assertIn('Тариф не подтверждён', quote.label)

    def test_baseline_record_without_tariff_falls_back_to_alternative_baseline(self):
        payload = standard_config()
        for item in payload['rates']:
            if item['provider'] == 'kie' and item['model'] == 'gpt-6-luna':
                item['input'] = None
                item['output'] = None
        registry = self.write_registry(payload)
        route = registry.route('openrouter', 'minimax/minimax-m3.1-flash:free')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(5000, 1000))
        self.assertEqual(quote.kind, 'reference_model')
        self.assertEqual(quote.provider, 'piapi')
        self.assertEqual(quote.model, 'gpt-5.6-luna')
        self.assertEqual(round(quote.cost_usd, 6), 0.000220)

    def test_alternative_baseline_is_taken_when_default_baseline_has_no_tariff(self):
        payload = config(
            rate('kie', 'gpt-6-luna', role='simple', input=None, output=None),
            rate('piapi', 'gpt-5.6-luna', role='extra', input=0.02, output=0.12),
            rate('openrouter', 'minimax/minimax-m3.1-flash:free', role='coding', input=0, output=0,
                 free=True, opt_in=True),
        )
        registry = self.write_registry(payload)
        route = registry.route('openrouter', 'minimax/minimax-m3.1-flash:free')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(5000, 1000))
        self.assertEqual(quote.kind, 'reference_model')
        self.assertEqual(quote.provider, 'piapi')
        self.assertEqual(quote.model, 'gpt-5.6-luna')
        # (5000 * 0.02 + 1000 * 0.12) / 1000000 = 0.000220
        self.assertEqual(round(quote.cost_usd, 6), 0.000220)

    def test_both_baselines_without_tariff_are_unavailable_without_number(self):
        payload = config(
            rate('kie', 'gpt-6-luna', role='simple', input=None, output=None),
            rate('piapi', 'gpt-5.6-luna', role='extra', input=None, output=None),
            rate('openrouter', 'minimax/minimax-m3.1-flash:free', role='coding', input=0, output=0,
                 free=True, opt_in=True),
        )
        registry = self.write_registry(payload)
        route = registry.route('openrouter', 'minimax/minimax-m3.1-flash:free')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(5000, 1000))
        self.assertEqual(quote.kind, 'unavailable')
        self.assertEqual(quote.status, 'unavailable')
        self.assertIsNone(quote.cost_usd)
        self.assertIn('Тариф не подтверждён', quote.label)
        self.assertNotIn('$0', quote.label)

    def test_same_model_tariff_is_taken_from_provider_with_filled_price(self):
        payload = config(
            rate('kie', 'gpt-5.6-luna', role='simple', input=None, output=None),
            rate('piapi', 'gpt-5.6-luna', role='extra', input=0.02, output=0.12),
        )
        registry = self.write_registry(payload)
        route = registry.route('piapi', 'gpt-5.6-luna')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(5000, 1000))
        self.assertEqual(quote.kind, 'exact_model')
        self.assertEqual(quote.provider, 'piapi')
        self.assertEqual(quote.model, 'gpt-5.6-luna')
        self.assertEqual(round(quote.cost_usd, 6), 0.000220)

    def test_partially_filled_tariff_is_unavailable_and_does_not_crash(self):
        payload = standard_config()
        payload['rates'][0]['output'] = None
        registry = self.write_registry(payload)
        route = registry.route('kie', 'gpt-6-luna')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(5000, 1000))
        self.assertEqual(quote.kind, 'unavailable')
        self.assertIsNone(quote.cost_usd)
        self.assertIn('Тариф не подтверждён', quote.label)

    def test_shipped_example_config_with_untariffed_record_gives_reference_without_crash(self):
        registry = llm_gateway.load_registry(str(EXAMPLE_PATH))
        route = registry.route('deepseek', 'deepseek-flash')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(5000, 1000))
        # тариф deepseek не заполнен, но ориентир берётся по заполненной базовой линии Kie GPT-6 Luna
        self.assertEqual(quote.kind, 'reference_model')
        self.assertEqual(quote.provider, 'kie')
        self.assertEqual(round(quote.cost_usd, 6), 0.000300)

    def test_reference_without_usage_stays_estimate_and_keeps_no_zero(self):
        registry = self.write_registry(standard_config())
        route = registry.route('kie', 'gpt-6-luna')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(None, None))
        self.assertEqual(quote.status, 'estimated')
        self.assertIsNone(quote.cost_usd)

    def test_micro_amounts_are_not_rounded_to_zero(self):
        registry = self.write_registry(standard_config())
        route = registry.route('kie', 'gpt-6-luna')
        quote = llm_gateway.reference_quote(registry, route, llm_gateway.Usage(1000, 100))
        # (1000 * 0.03 + 100 * 0.15) / 1000000 = 0.000045
        self.assertEqual(round(quote.cost_usd, 6), 0.000045)
        self.assertGreater(quote.cost_usd, 0)


class ActualQuoteTests(RegistryCase):
    """Фактическое списание: строго по тарифу провайдера, который выполнил вызов."""

    def test_actual_cost_uses_executing_provider_tariff_only(self):
        registry = self.write_registry(standard_config())
        route = registry.route('piapi', 'gpt-5.6-luna')
        quote = llm_gateway.actual_quote(registry, route, llm_gateway.Usage(5000, 1000))
        # (5000 * 0.02 + 1000 * 0.12) / 1000000 = 0.000220 — тариф PiAPI, не Kie
        self.assertEqual(round(quote.cost_usd, 6), 0.000220)
        self.assertNotEqual(round(quote.cost_usd, 6), 0.000300)
        self.assertEqual(quote.status, 'confirmed')
        self.assertEqual(quote.billing_source, 'provider_usage')
        self.assertEqual(quote.provider, 'piapi')
        self.assertEqual(quote.model, 'gpt-5.6-luna')

    def test_confirmed_free_route_costs_zero_with_free_status(self):
        registry = self.write_registry(standard_config())
        route = registry.route('openrouter', 'minimax/minimax-m3.1-flash:free')
        quote = llm_gateway.actual_quote(registry, route, llm_gateway.Usage(5000, 1000))
        self.assertEqual(quote.cost_usd, 0.0)
        self.assertEqual(quote.status, 'free')
        self.assertEqual(quote.billing_source, 'free_quota')

    def test_unknown_charge_is_not_zero(self):
        registry = self.write_registry(standard_config())
        route = registry.route('kie', 'gpt-6-luna')
        quote = llm_gateway.actual_quote(registry, route, None, charge_possible=True)
        self.assertIsNone(quote.cost_usd)
        self.assertEqual(quote.status, 'unknown')
        self.assertNotEqual(quote.cost_usd, 0)

    def test_paid_route_without_usage_is_never_confirmed_zero(self):
        # Платный маршрут без usage не бывает подтверждённым нулём: списание неизвестно.
        # charge_possible — флаг журнала, на расчёт не влияет.
        registry = self.write_registry(standard_config())
        route = registry.route('kie', 'gpt-6-luna')
        quote = llm_gateway.actual_quote(registry, route, None, charge_possible=False)
        self.assertIsNone(quote.cost_usd)
        self.assertEqual(quote.status, 'unknown')
        self.assertNotEqual(quote.cost_usd, 0)

    def test_route_without_confirmed_tariff_is_unknown_not_zero(self):
        registry = self.write_registry(standard_config())
        route = registry.route('deepseek', 'deepseek-flash')
        quote = llm_gateway.actual_quote(registry, route, llm_gateway.Usage(5000, 1000))
        self.assertIsNone(quote.cost_usd)
        self.assertEqual(quote.status, 'unknown')

    def test_actual_micro_amount_is_not_rounded_to_zero(self):
        registry = self.write_registry(standard_config())
        route = registry.route('kie', 'gpt-6-luna')
        quote = llm_gateway.actual_quote(registry, route, llm_gateway.Usage(1000, 100))
        # (1000 * 0.03 + 100 * 0.15) / 1000000 = 0.000045
        self.assertEqual(round(quote.cost_usd, 6), 0.000045)
        self.assertGreater(quote.cost_usd, 0)


class RouteSelectionTests(RegistryCase):
    """Выбор маршрута по задаче и по режиму работы."""

    def test_manual_mode_returns_requested_route(self):
        registry = self.write_registry(standard_config())
        route = llm_gateway.select_route(registry, 'gpt-6-luna', 'manual')
        self.assertIsNotNone(route)
        self.assertEqual((route.provider, route.model), ('kie', 'gpt-6-luna'))

    def test_auto_mode_uses_role(self):
        registry = self.write_registry(standard_config())
        route = llm_gateway.select_route(registry, 'editorial', 'auto')
        self.assertIsNotNone(route)
        self.assertEqual((route.provider, route.model), ('kie', 'claude-haiku-5-5'))

    def test_auto_mode_ignores_free_route_without_permission(self):
        registry = self.write_registry(standard_config())
        route = llm_gateway.select_route(registry, 'coding', 'auto')
        self.assertIsNotNone(route)
        self.assertEqual(route.provider, 'minimax')

    def test_disabled_route_is_not_selected(self):
        payload = standard_config()
        payload['rates'][0]['enabled'] = False
        registry = self.write_registry(payload)
        self.assertIsNone(llm_gateway.select_route(registry, 'gpt-6-luna', 'manual'))

    def test_free_route_needs_explicit_permission(self):
        registry = self.write_registry(standard_config())
        self.assertIsNone(llm_gateway.select_route(registry, 'minimax/minimax-m3.1-flash:free', 'manual'))
        route = llm_gateway.select_route(registry, 'minimax/minimax-m3.1-flash:free', 'manual', allow_free=True)
        self.assertIsNotNone(route)
        self.assertEqual(route.provider, 'openrouter')
        self.assertTrue(route.free)

    def test_unknown_task_and_mode_return_nothing(self):
        registry = self.write_registry(standard_config())
        self.assertIsNone(llm_gateway.select_route(registry, 'no-such-model', 'manual'))
        self.assertIsNone(llm_gateway.select_route(registry, 'simple', 'unknown-mode'))


class SpendSummaryTests(unittest.TestCase):
    """Сводка расходов: факт, резерв, неизвестные списания и неденежный ориентир — четырмя числами."""

    def make_db(self, columns, rows):
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        db.execute('CREATE TABLE llm_calls(' + ','.join(columns) + ')')
        for row in rows:
            placeholders = ','.join('?' * len(row))
            db.execute('INSERT INTO llm_calls VALUES(' + placeholders + ')', row)
        db.commit()
        self.addCleanup(db.close)
        return db

    def test_summary_splits_actual_reserved_unknown_and_reference(self):
        columns = ('id', 'request_id', 'project_id', 'model', 'status', 'usd', 'estimated_usd', 'input_tokens',
                   'output_tokens', 'created_at', 'execution_provider', 'execution_model', 'actual_cost_usd',
                   'actual_status', 'reserved_usd', 'billing_source', 'reference_provider', 'reference_model',
                   'reference_kind', 'reference_rate_snapshot_id', 'reference_cost_usd', 'reference_cost_status',
                   'cached_input_tokens', 'reasoning_tokens', 'price_snapshot_id', 'route_mode', 'fallback_from',
                   'error_kind', 'provider_request_id')
        rows = [
            ('1', 'r1', 'p1', 'gpt-6-luna', 'done', 0.0003, 0.0004, 5000, 1000, '2026-10-20T10:00:00', 'kie',
             'gpt-6-luna', 0.0003, 'confirmed', 0.001, 'provider_usage', 'kie', 'gpt-6-luna', 'exact_model',
             'snap-1', 0.0005, 'confirmed', None, None, 'snap-1', 'auto', None, None, 'req-1'),
            ('2', 'r2', 'p1', 'minimax/minimax-m3.1-flash:free', 'done', 0.0, 0.0002, 5000, 1000,
             '2026-10-20T10:01:00', 'openrouter', 'minimax/minimax-m3.1-flash:free', 0.0, 'free', 0.0,
             'free_quota', 'kie', 'gpt-6-luna', 'reference_model', 'snap-1', 0.0002, 'confirmed', None, None,
             'snap-1', 'auto', None, None, 'req-2'),
            ('3', 'r3', 'p1', 'gpt-6-luna', 'reserved', 0.001, 0.001, None, None, '2026-10-20T10:02:00', 'kie',
             'gpt-6-luna', None, None, 0.001, 'route_tariff', 'kie', 'gpt-6-luna', 'exact_model', 'snap-1',
             0.0001, 'estimated', None, None, 'snap-1', 'auto', None, None, 'req-3'),
            ('4', 'r4', 'p1', 'gpt-6-luna', 'failed', 0.002, 0.002, None, None, '2026-10-20T10:03:00', 'kie',
             'gpt-6-luna', None, 'unknown', 0.002, 'route_tariff', 'kie', 'gpt-6-luna', 'exact_model', 'snap-1',
             0.0003, 'estimated', None, None, 'snap-1', 'auto', None, 'http_5xx', 'req-4'),
            ('5', 'r5', 'p2', 'gpt-5.6-luna', 'done', 0.01, 0.01, 10000, 2000, '2026-10-20T10:04:00', 'piapi',
             'gpt-5.6-luna', 0.01, 'confirmed', 0.01, 'provider_usage', 'piapi', 'gpt-5.6-luna', 'exact_model',
             'snap-1', 0.01, 'confirmed', None, None, 'snap-1', 'auto', None, None, 'req-5'),
        ]
        db = self.make_db(columns, rows)
        summary = llm_gateway.summarize_spend(db, ['p1'])
        self.assertEqual(summary['calls'], 4)
        self.assertEqual(summary['actual_cost_usd'], 0.0003)
        self.assertEqual(summary['reserved_usd'], 0.001)
        self.assertEqual(summary['unknown_cost_usd'], 0.002)
        self.assertEqual(summary['reference_cost_usd'], 0.0011)
        other = llm_gateway.summarize_spend(db, ['p2'])
        self.assertEqual((other['calls'], other['actual_cost_usd']), (1, 0.01))

    def test_summary_reads_legacy_rows_by_usd(self):
        columns = ('id', 'request_id', 'project_id', 'model', 'status', 'usd', 'estimated_usd', 'input_tokens',
                   'output_tokens', 'created_at')
        rows = [
            ('1', 'r1', 'p1', 'gpt-5.6-luna', 'done', 0.5, 0.6, 100, 20, '2026-10-20T10:00:00'),
            ('2', 'r2', 'p1', 'gpt-5.6-luna', 'reserved', 0.25, 0.25, None, None, '2026-10-20T10:01:00'),
            ('3', 'r3', 'p1', 'gpt-5.6-luna', 'failed', 0.0, 0.3, None, None, '2026-10-20T10:02:00'),
        ]
        db = self.make_db(columns, rows)
        summary = llm_gateway.summarize_spend(db, ['p1'])
        self.assertEqual(summary['calls'], 3)
        self.assertEqual(summary['actual_cost_usd'], 0.5)
        self.assertEqual(summary['reserved_usd'], 0.25)
        self.assertEqual(summary['unknown_cost_usd'], 0.0)
        self.assertEqual(summary['reference_cost_usd'], 0.0)

    def test_summary_without_table_returns_zeros(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        summary = llm_gateway.summarize_spend(db, ['p1'])
        self.assertEqual(summary, {'actual_cost_usd': 0.0, 'reserved_usd': 0.0, 'unknown_cost_usd': 0.0,
                                    'reference_cost_usd': 0.0, 'calls': 0})
