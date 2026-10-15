"""Офлайн-тесты адаптеров моделей: параметры, тело запроса, цена. Сетевых вызовов нет."""
import unittest

from fastapi import HTTPException

from backend import adapters, main
from backend.image_assets import output_urls

REF = 'https://example.test/a.png'


def job(model, **extra):
    return main.ModelJobRequest(model_id=model, prompt=extra.pop('prompt', 'Taxi at night'), **extra)


def preview(model, **extra):
    body = job(model, **extra)
    payload = main.image_payload(body, enforce_launch=False)
    return payload, main.generation_cost(body, payload)


class AdapterTests(unittest.TestCase):
    def test_new_models_are_not_launchable_until_verified(self):
        for model in ('seedream-5-pro', 'nano-banana-2.1', 'qwen-image-2.1', 'gpt-image-2', 'gpt-image-2.5', 'minimax-h3'):
            with self.assertRaises(HTTPException) as caught:
                main.image_payload(job(model))
            self.assertEqual(caught.exception.status_code, 400, model)
            self.assertFalse(main.MODEL_SPECS[model].get('launch_enabled'), model)

    def test_existing_launchable_models_unchanged(self):
        payload = main.image_payload(job('seedream-5-lite'))
        self.assertEqual(payload['task_type'], 'seedream-5-lite')
        self.assertEqual(payload['input']['size'], '2K')
        self.assertEqual(main.generation_cost(job('seedream-5-lite'), payload), 0.052)

    def test_seedream_pro_price_and_options(self):
        payload, cost = preview('seedream-5-pro', options={'size': '2K'})
        self.assertEqual((payload['model'], payload['task_type']), ('seedream', 'seedream-5-pro'))
        self.assertEqual(cost, 0.136)
        _, with_refs = preview('seedream-5-pro', reference_urls=[REF, REF + '?2'])
        self.assertAlmostEqual(with_refs, 0.074, places=6)
        with self.assertRaises(HTTPException):
            preview('seedream-5-pro', options={'size': '3K'})
        with self.assertRaises(HTTPException):
            preview('seedream-5-pro', options={'n': 4})

    def test_nano_banana_21(self):
        payload, cost = preview('nano-banana-2.1', options={'resolution': '4K'})
        self.assertEqual((payload['model'], payload['task_type']), ('gemini', 'nano-banana-2.1'))
        self.assertEqual(cost, 0.09)

    def test_qwen_21_text_only(self):
        payload, cost = preview('qwen-image-2.1', options={'width': 1328, 'height': 1328})
        self.assertEqual(payload['model'], 'Qubico/qwen-image-2.1')
        self.assertEqual(payload['input']['steps'], 8)
        self.assertEqual(cost, 0.015)
        with self.assertRaises(HTTPException):
            preview('qwen-image-2.1', options={'width': 4096, 'height': 4096})
        with self.assertRaises(HTTPException):
            preview('qwen-image-2.1', reference_urls=[REF])
        with self.assertRaises(HTTPException):
            preview('qwen-image-2.1', options={'steps': 17})

    def test_gpt_image_variants_and_wire_body(self):
        spec = main.MODEL_SPECS['gpt-image-2.5']
        payload, cost = preview('gpt-image-2.5')
        self.assertEqual(payload['model'], 'gpt-image-2.5-flare')
        self.assertEqual(cost, 0.010)
        wire = adapters.wire_body(spec, payload)
        self.assertEqual(wire['model'], 'gpt-image-2.5-flare')
        self.assertEqual(wire['response_format'], 'url')
        self.assertEqual(adapters.submit_path(spec), '/api/v1/images/generations/async')
        standard, standard_cost = preview('gpt-image-2.5', options={'variant': 'standard'})
        self.assertEqual(standard['model'], 'gpt-image-2.5')
        self.assertNotIn('size', standard['input'])
        self.assertNotIn('quality', standard['input'])
        self.assertEqual(standard_cost, 0.012)
        _, tall = preview('gpt-image-2.5', options={'quality': 'high', 'size': '1024x1536'})
        self.assertEqual(tall, 0.06)
        with self.assertRaises(HTTPException):
            preview('gpt-image-2.5', reference_urls=[REF])

    def test_gpt_image_2_only_medium(self):
        _, cost = preview('gpt-image-2')
        self.assertEqual(cost, 0.032)
        with self.assertRaises(HTTPException):
            preview('gpt-image-2', options={'quality': 'high'})

    def test_minimax_h3_modes_and_price(self):
        payload, cost = preview('minimax-h3', options={'duration': 10, 'resolution': '768P'})
        self.assertEqual((payload['model'], payload['task_type']), ('Qubico/minimax-h3', 'txt2video'))
        self.assertEqual(cost, 0.5)
        image, _ = preview('minimax-h3', reference_urls=[REF])
        self.assertEqual(image['task_type'], 'img2video')
        self.assertEqual(image['input']['image'], REF)
        with self.assertRaises(HTTPException):
            preview('minimax-h3', options={'duration': 16})
        with self.assertRaises(HTTPException):
            preview('minimax-h3', reference_urls=[REF, REF + '?2'])

    def test_non_public_reference_rejected(self):
        with self.assertRaises(HTTPException):
            preview('seedream-5-pro', reference_urls=['http://example.test/a.png'])
        with self.assertRaises(HTTPException):
            preview('nano-banana-2.1', reference_urls=['https://localhost/a.png'])

    def test_output_shapes(self):
        gpt = {'data': {'output': {'data': [{'url': 'https://example.test/g.png'}]}}}
        self.assertEqual(output_urls(gpt), ['https://example.test/g.png'])
        nano = {'data': {'output': {'image_urls': ['https://example.test/n.png']}}}
        self.assertEqual(output_urls(nano), ['https://example.test/n.png'])
        minimax = {'data': {'output': {'video': 'https://example.test/v.mp4'}}}
        self.assertEqual(output_urls(minimax, 'video'), ['https://example.test/v.mp4'])


if __name__ == '__main__':
    unittest.main()
