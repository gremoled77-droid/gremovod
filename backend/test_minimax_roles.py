"""Реестр производственных ролей MiniMax: набор навыков на узел и разбор текстов.

Проверки не вызывают провайдера и не тратят бюджет: читаются только файлы навыков
из репозитория и реестр ролей.
"""
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend import minimax_roles, test_smoke


class MinimaxRolesTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def test_base_skill_is_in_every_stage_set(self):
        for stage_id in minimax_roles.ROLES:
            ids = [item['id'] for item in minimax_roles.stage_skills(stage_id)]
            self.assertIn(minimax_roles.BASE_SKILL, ids, stage_id)
            self.assertEqual(len(ids), len(set(ids)), stage_id)

    def test_canon_lock_sits_on_world_chars_and_board_only(self):
        for stage_id in ('world', 'chars', 'board'):
            ids = [item['id'] for item in minimax_roles.stage_skills(stage_id)]
            self.assertIn('skill-canon-lock', ids, stage_id)
        for stage_id in ('idea', 'frames', 'video', 'sound', 'edit', 'release'):
            ids = [item['id'] for item in minimax_roles.stage_skills(stage_id)]
            self.assertNotIn('skill-canon-lock', ids, stage_id)

    def test_video_prompt_crafter_sits_on_frames_and_video_only(self):
        for stage_id in ('frames', 'video'):
            ids = [item['id'] for item in minimax_roles.stage_skills(stage_id)]
            self.assertIn('skill-video-prompt-crafter', ids, stage_id)
        for stage_id in ('idea', 'world', 'chars', 'board', 'sound', 'edit', 'release'):
            ids = [item['id'] for item in minimax_roles.stage_skills(stage_id)]
            self.assertNotIn('skill-video-prompt-crafter', ids, stage_id)

    def test_gate_and_evidence_sets_carry_their_own_skills(self):
        gate = [item['id'] for item in minimax_roles.gate_skills()]
        self.assertIn('skill-precheck-filter', gate)
        self.assertIn(minimax_roles.BASE_SKILL, gate)
        evidence = [item['id'] for item in minimax_roles.evidence_skills()]
        self.assertIn('skill-evidence-packager', evidence)
        self.assertIn(minimax_roles.BASE_SKILL, evidence)
        self.assertNotIn('skill-precheck-filter', evidence)

    def test_unknown_stage_is_a_400_with_the_list_of_nodes(self):
        with self.assertRaises(HTTPException) as caught:
            minimax_roles.stage_skills('nope')
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn('board', caught.exception.detail)

    def test_alias_resolves_to_the_canonical_skill(self):
        self.assertEqual(minimax_roles.canonical_id('skill-cheap-gatekeeper'), 'skill-precheck-filter')
        self.assertEqual(minimax_roles.canonical_id('skill-canon-lock'), 'skill-canon-lock')
        self.assertEqual(minimax_roles.skill_path('skill-cheap-gatekeeper'),
                         minimax_roles.skill_path('skill-precheck-filter'))

    def test_instructions_carry_no_frontmatter(self):
        for skill_id in ('skill-strict-json-output', 'skill-canon-lock',
                         'skill-video-prompt-crafter', 'skill-precheck-filter',
                         'skill-evidence-packager'):
            skill = minimax_roles.load_skill(skill_id)
            self.assertTrue(skill['available'], skill_id)
            self.assertFalse(skill['instructions'].startswith('---'), skill_id)
            self.assertTrue(skill['title'], skill_id)
            self.assertEqual(len(skill['version']), 12, skill_id)

    def test_skill_texts_keep_their_contract(self):
        strict = minimax_roles.load_skill('skill-strict-json-output')['instructions']
        self.assertIn('BLOCKED_INVALID_INPUT', strict)
        self.assertIn('ЗАПРЕЩЕНО', strict)
        canon = minimax_roles.load_skill('skill-canon-lock')['instructions']
        self.assertIn('[CANON]', canon)
        crafter = minimax_roles.load_skill('skill-video-prompt-crafter')['instructions']
        self.assertIn('found_footage', crafter)
        self.assertIn('handheld camera shake', crafter)
        precheck = minimax_roles.load_skill('skill-precheck-filter')['instructions']
        self.assertIn('REJECTED_PRECHECK', precheck)
        evidence = minimax_roles.load_skill('skill-evidence-packager')['instructions']
        self.assertIn('sha256', evidence)
        self.assertIn('timecode_ms', evidence)

    def test_missing_skill_file_is_skipped_not_fatal(self):
        with patch.object(minimax_roles, 'SKILLS_ROOT', minimax_roles.SKILLS_ROOT / 'nope'):
            self.assertEqual(minimax_roles.stage_skills('board'), [])
            self.assertIn('skill-canon-lock', minimax_roles.missing_skills())
            self.assertIn(minimax_roles.BASE_SKILL, minimax_roles.missing_skills())

    def test_endpoint_serves_the_registry(self):
        data = self.client.get('/api/llm/roles').json()
        self.assertEqual(data['base_skill'], minimax_roles.BASE_SKILL)
        self.assertEqual(sorted(data['stages']), sorted(minimax_roles.ROLES))
        self.assertEqual(data['missing_skills'], [])
        frame_skills = data['stages']['frames']['skills']
        self.assertIn('skill-video-prompt-crafter', [item['id'] for item in frame_skills])
        self.assertTrue(all(item['instructions'].strip() for item in frame_skills))

    def test_endpoint_filters_by_stage(self):
        data = self.client.get('/api/llm/roles?stage=frames').json()
        self.assertEqual(data['stage'], 'frames')
        self.assertIn('skill-video-prompt-crafter', [item['id'] for item in data['skills']])
        self.assertEqual(self.client.get('/api/llm/roles?stage=nope').status_code, 400)


if __name__ == '__main__':
    unittest.main()
