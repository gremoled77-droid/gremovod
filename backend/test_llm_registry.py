"""Реестр LLM: backend — источник истины, frontend хранит копию для рендера.

frontend/src/llmPricing.ts нужен синхронно (модель и цена нужны во время рендера),
поэтому это копия. Расхождение копии с реестром ломает оценку и подтверждение,
так что соответствие проверяется здесь.
"""
import re
import unittest
from pathlib import Path

from backend.model_catalog import LLM_MODELS, llm_scope

FRONTEND = Path(__file__).resolve().parents[1] / 'frontend' / 'src' / 'llmPricing.ts'
ENTRY = re.compile(r"'([^']+)':\s*\{label:\s*'([^']*)',\s*input:\s*([0-9.]+),\s*output:\s*([0-9.]+)\}")


def frontend_models(source, name):
    """Записи из объявленного в llmPricing.ts списка."""
    block = re.search(rf'export const {name}[^=]*=\s*\{{(.*?)\n\}};', source, re.S)
    assert block, f'Не найден список {name} в llmPricing.ts'
    return {key:{'label':label,'input':float(price_in),'output':float(price_out)}
            for key,label,price_in,price_out in ENTRY.findall(block.group(1))}


class LlmRegistryTests(unittest.TestCase):
    def setUp(self):
        self.source = FRONTEND.read_text(encoding='utf-8')

    def test_workflow_models_match_backend(self):
        self.assertEqual(frontend_models(self.source,'LLM_MODELS'), {
            key:{'label':spec['label'],'input':spec['price_in'],'output':spec['price_out']}
            for key,spec in LLM_MODELS.items() if 'workflow' in spec['scopes']})

    def test_idea_models_match_backend(self):
        # IDEA_LLM_MODELS собран как {...LLM_MODELS, 'gpt-6-astra': ...}
        models = frontend_models(self.source, 'LLM_MODELS')
        models.update(frontend_models(self.source, 'IDEA_LLM_MODELS'))
        self.assertEqual(models, {
            key:{'label':spec['label'],'input':spec['price_in'],'output':spec['price_out']}
            for key,spec in LLM_MODELS.items() if 'idea' in spec['scopes']})

    def test_prices_are_not_duplicated_in_backend(self):
        from backend import llm_guard
        self.assertEqual(llm_guard.PRICES, {
            key:(spec['price_in'],spec['price_out'])
            for key,spec in LLM_MODELS.items() if set(('workflow','idea'))&set(spec['scopes'])})
        self.assertEqual(llm_guard.MINIMAX_PRICES, {
            key:(spec['price_in'],spec['price_out'])
            for key,spec in LLM_MODELS.items() if 'task' in spec['scopes']})

    def test_only_registered_models_are_allowed(self):
        from backend.model_catalog import ALLOWED_CHAT
        self.assertEqual(ALLOWED_CHAT, llm_scope('workflow')|llm_scope('idea'))
        self.assertNotIn('gpt-4.1-mini', ALLOWED_CHAT)

    def test_frontend_estimate_is_not_below_backend_estimate(self):
        """Предпросмотр цены во фронтенде не должен быть дешевле оценки, которую enforced backend."""
        from backend import llm_guard
        divisor = float(re.search(r'inputChars\s*/\s*([\d.]+)', self.source).group(1))
        self.assertEqual(divisor, llm_guard.INPUT_CHARS_PER_TOKEN,
                         'фронтенд и backend считают входные токены по-разному')
        for key, spec in LLM_MODELS.items():
            if 'workflow' not in spec['scopes']:
                continue
            chars = 4000
            backend = llm_guard.estimate_usd(key, [{'role': 'user', 'content': 'x' * chars}], llm_guard.MAX_OUTPUT_TOKENS)
            frontend = ((chars / divisor + 50) * spec['price_in']
                        + llm_guard.MAX_OUTPUT_TOKENS * spec['price_out']) / 1_000_000
            self.assertGreaterEqual(frontend, backend, f'{key}: предпросмотр дешевле оценки backend')


if __name__ == '__main__':
    unittest.main()
