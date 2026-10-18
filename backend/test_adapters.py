"""Офлайн-тесты адаптеров моделей: параметры, тело запроса, цена. Сетевых вызовов нет."""
import unittest

from fastapi import HTTPException

from backend import adapters, kie, main
from backend.image_assets import output_urls

REF = 'https://example.test/a.png'


def job(model, **extra):
    return main.ModelJobRequest(model_id=model, prompt=extra.pop('prompt', 'Taxi at night'), **extra)


def preview(model, **extra):
    body = job(model, **extra)
    payload = main.image_payload(body, enforce_launch=False)
    return payload, main.generation_cost(body, payload)


class AdapterTests(unittest.TestCase):
    def test_live_verified_models_are_launchable_with_date(self):
        for model in ('seedream-5-pro', 'nano-banana-2.1', 'qwen-image-2.1', 'gpt-image-2', 'gpt-image-2.5', 'minimax-h3'):
            spec = main.MODEL_SPECS[model]
            self.assertTrue(spec['launch_enabled'], model)
            self.assertEqual(spec['verified_at'], '2026-10-16', model)
            self.assertEqual(main.image_payload(job(model))['model'], spec['model'] if model != 'gpt-image-2' and model != 'gpt-image-2.5' else main.image_payload(job(model))['model'])

    def test_sunburst_edits_stay_blocked(self):
        with self.assertRaises(HTTPException):
            main.image_payload(job('gpt-image-2.5', reference_urls=['https://example.com/a.png']))

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
        payload, cost = preview('minimax-h3', options={'duration': 10, 'resolution': '768p'})
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


class UpscaleAdapterTests(unittest.TestCase):
    """Апскейл: параметры и цена по документации PiAPI, запуск выключен до живой проверки."""

    def test_upscale_is_preview_only_and_priced_per_megapixel(self):
        spec = main.MODEL_SPECS['image-upscale']
        self.assertFalse(spec['launch_enabled'])
        self.assertIsNone(spec.get('verified_at'))
        with self.assertRaises(HTTPException):
            main.image_payload(job('image-upscale', prompt='Upscale', reference_urls=[REF]))  # запуск заблокирован
        payload, cost = preview('image-upscale', prompt='Upscale', reference_urls=[REF],
                                options={'scale': 2, 'in_width': 1024, 'in_height': 1024})
        self.assertEqual(cost, 0.004)  # 1024² ×2 = 4 Мп (пример из документации)
        self.assertEqual((payload['model'], payload['task_type']), ('Qubico/image-toolkit', 'upscale'))
        _, big = preview('image-upscale', prompt='Upscale', reference_urls=[REF], options={'scale': 4})
        self.assertEqual(big, 0.064)  # потолок: 2048² ×4 = 64 Мп (пример из документации)
        _, tiny = preview('image-upscale', prompt='Upscale', reference_urls=[REF],
                          options={'scale': 2, 'in_width': 480, 'in_height': 480})
        self.assertEqual(tiny, 0.001)  # меньше 1 Мп, минимум $0.001
        _, unknown = preview('image-upscale', prompt='Upscale', reference_urls=[REF])
        self.assertEqual(unknown, 0.016)  # без размеров входа: максимум 2048² ×2

    def test_upscale_wire_body_has_no_internal_fields_and_inputs_are_checked(self):
        body = job('image-upscale', prompt='Upscale', reference_urls=[REF], options={'scale': 4, 'in_width': 800, 'in_height': 600})
        payload = main.image_payload(body, enforce_launch=False)
        spec = main.MODEL_SPECS['image-upscale']
        self.assertEqual(adapters.wire_body(spec, payload), {'model': 'Qubico/image-toolkit', 'task_type': 'upscale',
                                                           'input': {'image': REF, 'scale': 4}})
        self.assertEqual(adapters.submit_path(spec), '/api/v1/task')
        for bad in (dict(reference_urls=[]), dict(reference_urls=[REF, REF + '?2']),
                    dict(reference_urls=['http://example.test/a.png']), dict(reference_urls=['https://localhost/a.png']),
                    dict(reference_urls=[REF], options={'scale': 8}), dict(reference_urls=[REF], options={'scale': 3}),
                    dict(reference_urls=[REF], options={'in_width': 4096}), dict(reference_urls=[REF], options={'face_enhance': True})):
            with self.assertRaises(HTTPException, msg=str(bad)):
                preview('image-upscale', prompt='Upscale', **bad)

    def test_upscale_result_is_read_from_documented_or_example_shape(self):
        schema = {'data': {'task_result': {'task_output': {'image_url': 'https://example.test/u.png'}}}}
        example = {'data': {'output': {'image_url': 'https://example.test/e.png'}}}
        self.assertEqual(output_urls(schema), ['https://example.test/u.png'])
        self.assertEqual(output_urls(example), ['https://example.test/e.png'])
        self.assertEqual(output_urls({'data': {'output': None, 'task_result': None}}), [])


class SeedTests(unittest.TestCase):
    """seed есть в документации PiAPI только у MiniMax H3: необязательный, без него тело запроса прежнее."""

    def test_minimax_seed_is_optional_and_checked(self):
        without, _ = preview('minimax-h3')
        self.assertNotIn('seed', without['input'])
        with_seed, cost = preview('minimax-h3', options={'seed': 42})
        self.assertEqual(with_seed['input']['seed'], 42)
        self.assertEqual(cost, 0.15)  # seed цену не меняет
        for bad in (-1, 2 ** 31, 'abc', 1.5, True):
            with self.assertRaises(HTTPException, msg=str(bad)):
                preview('minimax-h3', options={'seed': bad})

    def test_other_video_models_do_not_take_seed(self):
        with self.assertRaises(HTTPException):
            preview('seedance-2.5', options={'seed': 1})


if __name__ == '__main__':
    unittest.main()


class ProviderShapeTests(unittest.TestCase):
    def test_gpt_b64_output_becomes_inline_image(self):
        import base64, io
        from PIL import Image
        from backend.image_assets import output_urls, download_image
        import asyncio
        buf = io.BytesIO(); Image.new('RGB', (4, 4)).save(buf, 'PNG')
        resp = {'data': {'output': {'data': [{'b64_json': base64.b64encode(buf.getvalue()).decode()}]}}}
        urls = output_urls(resp, 'image')
        self.assertTrue(urls[0].startswith('data:image/png;base64,'))
        self.assertEqual(asyncio.run(download_image(urls[0])), buf.getvalue())


class KieTests(unittest.TestCase):
    def test_kie_models_preview_only_and_priced_from_kie_pages(self):
        for model in ('kie-seedream-5-pro', 'kie-qwen-image-2.1'):
            spec = main.MODEL_SPECS[model]
            self.assertEqual((spec['provider'], spec['launch_enabled']), ('kie', False))
            self.assertEqual(spec['page_urls'], {'kie': spec['docs']})
        payload, cost = preview('kie-seedream-5-pro', reference_urls=[REF] * 3)
        self.assertEqual((payload['input']['quality'], cost), ('basic', 0.04))  # 7 кредитов + 2 × 0.5
        payload, cost = preview('kie-qwen-image-2.1', reference_urls=[REF] * 3, options={'resolution': '2K'})
        self.assertEqual(cost, 0.04)
        self.assertFalse(payload['input']['enhance_prompt'])
        self.assertEqual(adapters.wire_body(main.MODEL_SPECS['kie-qwen-image-2.1'], payload),
                         {'model': 'qwen2-1/image-to-image', 'input': payload['input']})

    def test_kie_rejects_text_only_unknown_options_and_long_prompt(self):
        for extra in ({}, {'reference_urls': [REF], 'options': {'size': '2K'}},
                      {'reference_urls': [REF], 'prompt': 'x' * 5001}):
            with self.assertRaises(HTTPException):
                preview('kie-seedream-5-pro', **extra)

    def test_kie_status_normalized_to_piapi_shape(self):
        done = kie.status({'code': 200, 'data': {'taskId': 't1', 'state': 'success',
                                                 'resultJson': '{"resultUrls":["https://cdn.test/1.png","http://bad"]}'}})
        self.assertEqual(output_urls(done), ['https://cdn.test/1.png'])
        self.assertEqual(done['data']['status'], 'completed')
        self.assertEqual(kie.status({'code': 200, 'data': {'state': 'generating'}})['data']['status'], 'processing')
        failed = kie.status({'code': 200, 'data': {'state': 'fail', 'failMsg': 'nsfw'}})['data']
        self.assertEqual((failed['status'], failed['error']['message']), ('failed', 'nsfw'))
        self.assertEqual(kie.submitted({'code': 200, 'data': {}})['data'], {})
