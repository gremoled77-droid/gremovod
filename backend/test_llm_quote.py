"""Подпись оценки LLM: старая форма принимается, новая связывает провайдера, модель, версию цены,
запасной маршрут и допустимый максимум платежа."""
import json
import unittest

from fastapi import HTTPException

from backend import security

PAYLOAD = {'kind': 'llm', 'model': 'gpt-6-luna', 'max_tokens': 500, 'messages': 'digest-of-messages'}
COST = 0.000308
EXTRA = {'provider': 'kie', 'model': 'gpt-6-luna', 'price_version': 'kie/gpt-6-luna@2026-10-20',
         'fallback': ['deepseek/deepseek-flash'], 'max_payment_usd': COST, 'tools_hash': 'digest-of-tools'}


class QuoteWithoutExtraTests(unittest.TestCase):
    """Старые подписи (без extra) принимаются как прежде."""

    def test_old_token_is_accepted_by_old_call(self):
        token = security.quote('project-1', PAYLOAD, COST)
        self.assertEqual(security.verify_quote(token, 'project-1', PAYLOAD, COST), (True, 'ok'))

    def test_old_token_keeps_its_wire_shape(self):
        data = json.loads(security.quote('project-1', PAYLOAD, COST).rsplit('.', 1)[0])
        self.assertEqual(sorted(data), ['cost', 'expires', 'payload', 'project_id'])
        self.assertNotIn('extra', data)

    def test_old_token_still_rejects_other_project_cost_and_payload(self):
        token = security.quote('project-1', PAYLOAD, COST)
        for args in (('project-2', PAYLOAD, COST), ('project-1', {**PAYLOAD, 'model': 'other'}, COST),
                     ('project-1', PAYLOAD, COST * 2)):
            with self.assertRaises(HTTPException):
                security.verify_quote(token, *args)


class QuoteWithExtraTests(unittest.TestCase):
    """Новая подпись связывает маршрут и максимум платежа."""

    def test_new_token_is_accepted_with_the_same_extra(self):
        token = security.quote('project-1', PAYLOAD, COST, EXTRA)
        self.assertEqual(security.verify_quote(token, 'project-1', PAYLOAD, COST, EXTRA), (True, 'ok'))

    def test_tampered_extra_is_rejected(self):
        token = security.quote('project-1', PAYLOAD, COST, EXTRA)
        for field, value in (('provider', 'piapi'), ('model', 'gpt-5.6-luna'),
                             ('price_version', 'kie/gpt-6-luna@2026-01-01'), ('fallback', None),
                             ('max_payment_usd', 10.0), ('tools_hash', 'other-digest')):
            with self.assertRaises(HTTPException):
                security.verify_quote(token, 'project-1', PAYLOAD, COST, {**EXTRA, field: value})

    def test_token_with_extra_is_not_accepted_as_an_old_one(self):
        token = security.quote('project-1', PAYLOAD, COST, EXTRA)
        with self.assertRaises(HTTPException):
            security.verify_quote(token, 'project-1', PAYLOAD, COST)

    def test_old_token_is_not_accepted_with_a_new_extra(self):
        token = security.quote('project-1', PAYLOAD, COST)
        with self.assertRaises(HTTPException):
            security.verify_quote(token, 'project-1', PAYLOAD, COST, EXTRA)

    def test_extra_is_bound_to_project_cost_and_payload(self):
        token = security.quote('project-1', PAYLOAD, COST, EXTRA)
        for args in (('project-2', PAYLOAD, COST, EXTRA), ('project-1', {**PAYLOAD, 'max_tokens': 501}, COST, EXTRA),
                     ('project-1', PAYLOAD, COST * 2, EXTRA)):
            with self.assertRaises(HTTPException):
                security.verify_quote(token, *args)


if __name__ == '__main__':
    unittest.main()
