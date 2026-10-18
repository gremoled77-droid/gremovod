"""Офлайн-тесты адаптера Seedance 2.5: видео и аудио референсы, edit/extend, draft, цена. Сетевых вызовов нет."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend import adapters, main

IMG = 'https://cdn.example.test/frame.png'
VID = 'https://cdn.example.test/source.mp4'
AUD = 'https://cdn.example.test/voice.mp3'
SPEC = main.MODEL_SPECS['seedance-2.5']


def req(prompt='Slow dolly in', **extra):
    return main.ModelJobRequest(model_id='seedance-2.5', prompt=prompt, **extra)


def preview(prompt='Slow dolly in', draft=None, **extra):
    body = req(prompt, **extra)
    payload = adapters.build(SPEC, body, draft=draft)
    return payload, adapters.cost(SPEC, payload)


class SeedanceAdapterTests(unittest.TestCase):
    def test_launch_flag_and_adapter(self):
        self.assertFalse(SPEC['launch_enabled'])  # живого вызова не было
        self.assertEqual(SPEC['adapter'], 'seedance_25')

    def test_text_only_and_image_reference_unchanged(self):
        payload, cost = preview()
        self.assertEqual(payload['input'], {'prompt': 'Slow dolly in', 'resolution': '480p', 'duration': 5,
                                            'aspect_ratio': '16:9', 'mode': 'text_to_video'})
        self.assertEqual(cost, 0.75)
        payload, cost = preview('Move @image1', reference_urls=[IMG])
        self.assertEqual(payload['input']['mode'], 'omni_reference')
        self.assertEqual(payload['input']['omni_reference_task_type'], 'reference')
        self.assertEqual(payload['input']['image_urls'], [IMG])
        self.assertEqual(cost, 0.75)

    def test_video_and_audio_references_price_and_wire(self):
        payload, cost = preview('Style of @image1 with @video1 motion and @audio1 soundtrack',
                                reference_urls=[IMG], video_urls=[VID], audio_urls=[AUD],
                                options={'duration': 10, 'resolution': '720p', 'video_seconds': 6, 'audio_seconds': 8})
        self.assertEqual(payload['input']['video_urls'], [VID])
        self.assertEqual(payload['input']['audio_urls'], [AUD])
        self.assertEqual(cost, round(0.35 * 10 + 0.175 * 6, 3))  # выход + половина цены за секунды входного видео
        wire = adapters.wire_body(SPEC, payload)
        self.assertNotIn('billing', wire)
        self.assertNotIn('video_seconds', wire['input'])
        self.assertNotIn('audio_seconds', wire['input'])
        lines = adapters.describe(SPEC, payload)
        self.assertTrue(any('Входное видео 6' in line for line in lines))
        self.assertTrue(any('видео 1' in line for line in lines))

    def test_audio_only_allowed_but_needs_seconds(self):
        payload, cost = preview('Sing along @audio1', audio_urls=[AUD], options={'audio_seconds': 12})
        self.assertEqual(payload['input']['mode'], 'omni_reference')
        self.assertEqual(cost, 0.75)
        with self.assertRaises(HTTPException):
            preview('Sing along @audio1', audio_urls=[AUD])
        with self.assertRaises(HTTPException):
            preview('Sing along @audio1', audio_urls=[AUD], options={'audio_seconds': 31})

    def test_extend_requires_source_video_and_adaptive(self):
        payload, cost = preview('Extend @video1 forward: the camera keeps drifting', video_urls=[VID],
                                options={'task': 'extend', 'duration': 8, 'video_seconds': 5})
        self.assertEqual(payload['input']['omni_reference_task_type'], 'extend')
        self.assertEqual(payload['input']['aspect_ratio'], 'adaptive')
        self.assertEqual(payload['input']['duration'], 8)
        self.assertEqual(cost, round(0.15 * 8 + 0.075 * 5, 3))
        with self.assertRaises(HTTPException):
            preview('Extend', options={'task': 'extend', 'duration': 8})
        with self.assertRaises(HTTPException):
            preview('Extend @video1', video_urls=[VID], options={'task': 'extend', 'duration': 8, 'video_seconds': 5, 'aspect_ratio': '16:9'})

    def test_edit_uses_source_length_and_minus_one(self):
        payload, cost = preview('In @video1, change the lighting to golden hour', video_urls=[VID],
                                options={'task': 'edit', 'video_seconds': 10})
        self.assertEqual(payload['input']['duration'], -1)
        self.assertEqual(payload['input']['aspect_ratio'], 'adaptive')
        self.assertEqual(cost, round(0.15 * 10 + 0.075 * 10, 3))
        self.assertTrue(any('правка' in line for line in adapters.describe(SPEC, payload)))
        for bad in ({'task': 'edit', 'video_seconds': 3}, {'task': 'edit', 'video_seconds': 31},
                    {'task': 'edit', 'video_seconds': 10, 'duration': 5}):
            with self.assertRaises(HTTPException):
                preview('In @video1, change', video_urls=[VID], options=bad)

    def test_draft_is_480p_only_and_flagged(self):
        payload, cost = preview(options={'draft': True, 'duration': 6})
        self.assertTrue(payload['input']['draft'])
        self.assertEqual(payload['input']['resolution'], '480p')
        self.assertEqual(cost, 0.9)
        self.assertTrue(any('Черновик 480p' in line for line in adapters.describe(SPEC, payload)))
        with self.assertRaises(HTTPException):
            preview(options={'draft': True, 'resolution': '720p'})
        with self.assertRaises(HTTPException):
            preview(options={'draft': False})

    def test_final_from_draft_wire_body_has_no_prompt_or_refs(self):
        draft = {'resolution': '480p', 'duration_s': 6, 'video_s': 0}
        payload, cost = preview('ignored by provider', draft=draft, options={'draft_task_id': 'task-abc_123'})
        self.assertEqual(payload['input'], {'draft_task_id': 'task-abc_123', 'resolution': '1080p'})
        self.assertEqual(cost, round(0.8 * 6, 3))
        wire = adapters.wire_body(SPEC, payload)
        self.assertEqual(set(wire), {'model', 'task_type', 'input'})
        self.assertTrue(any('Финал 1080p' in line for line in adapters.describe(SPEC, payload)))

    def test_final_with_draft_video_references_bills_input_at_half_1080p(self):
        draft = {'resolution': '480p', 'duration_s': 6, 'video_s': 10}
        _, cost = preview(draft=draft, options={'draft_task_id': 'abc'})
        self.assertEqual(cost, round(0.8 * 6 + 0.4 * 10, 3))

    def test_final_from_draft_rejects_conflicts(self):
        draft = {'resolution': '480p', 'duration_s': 6, 'video_s': 0}
        for kwargs in (
            dict(options={'draft_task_id': 'abc'}, draft=None),
            dict(options={'draft_task_id': 'abc', 'draft': True}, draft=draft),
            dict(options={'draft_task_id': 'abc', 'duration': 6}, draft=draft),
            dict(options={'draft_task_id': 'abc', 'resolution': '720p'}, draft=draft),
            dict(options={'draft_task_id': 'abc'}, draft=draft, reference_urls=[IMG]),
            dict(options={'draft_task_id': 'a b'}, draft=draft),
        ):
            with self.assertRaises(HTTPException, msg=str(kwargs)):
                preview(**kwargs)

    def test_tag_and_limit_validation(self):
        for bad in (dict(prompt='Move @video1'), dict(prompt='Move @image2', reference_urls=[IMG]),
                    dict(prompt='Move @audio1', reference_urls=[IMG]),
                    dict(options={'task': 'auto'}, reference_urls=[IMG]),
                    dict(options={'task': 'reference'}),
                    dict(options={'generate_audio': True}),
                    dict(options={'duration': 5.5}), dict(options={'duration': 31}), dict(options={'resolution': '4K'}),
                    dict(options={'video_seconds': 5}),
                    dict(reference_urls=['http://cdn.example.test/a.png']),
                    dict(video_urls=['https://localhost/a.mp4'], options={'video_seconds': 5})):
            with self.assertRaises(HTTPException, msg=str(bad)):
                preview(**bad)

    def test_other_models_do_not_accept_video_or_audio(self):
        for model in ('seedream-5-lite', 'minimax-h3'):
            body = main.ModelJobRequest(model_id=model, prompt='x', video_urls=[VID])
            with self.assertRaises(HTTPException):
                main.image_payload(body, enforce_launch=False)

    @patch.dict(SPEC, {'launch_enabled': True})
    def test_main_pipeline_estimate_matches_adapter(self):
        body = req('Extend @video1 forward: drifting', video_urls=[VID],
                   options={'task': 'extend', 'duration': 8, 'video_seconds': 5})
        payload = main.image_payload(body)
        self.assertEqual(main.generation_cost(body, payload), round(0.15 * 8 + 0.075 * 5, 3))


if __name__ == '__main__':
    unittest.main()
