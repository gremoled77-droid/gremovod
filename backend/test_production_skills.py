"""Производственные скиллы бэкенда: целостность реестра, сборка промпта, договорённости.

Проверки бесплатные: ни одного сетевого вызова, ни одного платного API.
"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from backend import production_skills

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'docs/specs/n8n-production-2026-10-19/contracts/scenario-skills-routing-v1.json'
IDS = ['skill-strict-json-output', 'skill-canon-lock', 'skill-video-prompt-crafter', 'skill-cheap-gatekeeper']
LLM_ENGINES = {'BOUNDED_LLM', 'CREATIVE_LLM', 'DIRECTOR_LLM', 'BOUNDED_LLM_AND_CODE', 'RESEARCH_ON_DEMAND'}


def routing():
    return json.loads(CONTRACT.read_text(encoding='utf-8'))


class ProductionSkillsRegistry(unittest.TestCase):
    def test_registry_lists_four_skills(self):
        self.assertEqual(production_skills.available(), IDS)

    def test_skill_files_exist(self):
        for item in production_skills.registry()['skills']:
            self.assertTrue((production_skills.SKILLS_ROOT / item['file']).is_file(), item['id'])

    def test_skill_hash_matches_registry(self):
        for item in production_skills.registry()['skills']:
            body = (production_skills.SKILLS_ROOT / item['file']).read_text(encoding='utf-8')
            self.assertEqual(production_skills.digest(body), item['sha256'], item['id'])

    def test_unknown_skill_is_rejected(self):
        with self.assertRaises(production_skills.SkillError):
            production_skills.text('skill-not-in-registry')
        with self.assertRaises(production_skills.SkillError):
            production_skills.bundle(['skill-strict-json-output', 'skill-not-in-registry'])

    def test_missing_skill_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'registry.json').write_text(json.dumps({'skills': [
                {'id': 'skill-missing', 'file': 'skill-missing/SKILL.md', 'sha256': '0' * 64, 'version': '1.0'}]}), encoding='utf-8')
            with mock.patch.object(production_skills, 'SKILLS_ROOT', root), \
                 mock.patch.object(production_skills, 'REGISTRY_PATH', root / 'registry.json'), \
                 mock.patch.dict(production_skills._cache, {}, clear=True):
                with self.assertRaises(production_skills.SkillError):
                    production_skills.text('skill-missing')

    def test_hash_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'skill-drift').mkdir()
            (root / 'skill-drift' / 'SKILL.md').write_text('изменённый текст', encoding='utf-8')
            body = (root / 'skill-drift' / 'SKILL.md').read_text(encoding='utf-8')
            (root / 'registry.json').write_text(json.dumps({'skills': [
                {'id': 'skill-drift', 'file': 'skill-drift/SKILL.md', 'sha256': production_skills.digest(body), 'version': '1.0'}]}), encoding='utf-8')
            with mock.patch.object(production_skills, 'SKILLS_ROOT', root), \
                 mock.patch.object(production_skills, 'REGISTRY_PATH', root / 'registry.json'), \
                 mock.patch.dict(production_skills._cache, {}, clear=True):
                production_skills.text('skill-drift')
                (root / 'skill-drift' / 'SKILL.md').write_text('изменённый текст ещё раз', encoding='utf-8')
                with self.assertRaises(production_skills.SkillError):
                    production_skills.text('skill-drift')


class ProductionSkillsComposition(unittest.TestCase):
    def test_bundle_keeps_registry_order_and_dedups(self):
        bundle = production_skills.bundle(['skill-cheap-gatekeeper', 'skill-strict-json-output', 'skill-strict-json-output'])
        self.assertEqual(bundle, ['skill-strict-json-output', 'skill-cheap-gatekeeper'])

    def test_system_prompt_without_skills_returns_base_unchanged(self):
        self.assertEqual(production_skills.system_prompt('БАЗА', []), 'БАЗА')
        self.assertEqual(production_skills.system_prompt('БАЗА', None), 'БАЗА')

    def test_system_prompt_contains_skill_text(self):
        prompt = production_skills.system_prompt('БАЗА', ['skill-strict-json-output'])
        self.assertTrue(prompt.startswith('БАЗА\n\n'))
        self.assertIn(production_skills.text('skill-strict-json-output'), prompt)

    def test_bundle_hash_is_stable_and_differs_between_bundles(self):
        first = production_skills.bundle_hash(['skill-strict-json-output'])
        self.assertEqual(first, production_skills.bundle_hash(['skill-strict-json-output']))
        self.assertNotEqual(first, production_skills.bundle_hash(['skill-canon-lock']))

    def test_native_chat_bundle_selection(self):
        self.assertEqual(production_skills.for_native_chat('describe_character', 'image'), ['skill-canon-lock'])
        self.assertEqual(production_skills.for_native_chat('prompt', 'video'), ['skill-video-prompt-crafter'])
        self.assertEqual(production_skills.for_native_chat('prompt', 'video', has_canon=True),
                         ['skill-canon-lock', 'skill-video-prompt-crafter'])
        self.assertEqual(production_skills.for_native_chat('edit', 'image'), [])


class ProductionSkillsContracts(unittest.TestCase):
    def test_strict_json_covers_every_llm_stage(self):
        stages = [stage for stage in routing()['stages'] if stage['engine'] in LLM_ENGINES]
        self.assertTrue(stages)
        for stage in stages:
            self.assertIn('skill-strict-json-output', production_skills.for_stage(stage['id']), stage['id'])

    def test_skill_contract_markers(self):
        strict = production_skills.text('skill-strict-json-output')
        self.assertIn('BLOCKED_INVALID_INPUT', strict)
        self.assertIn('ЗАПРЕЩЕНО оборачивать ответ в блоки', strict)
        canon = production_skills.text('skill-canon-lock')
        self.assertIn('canon_revision_id', canon)
        self.assertIn('[CANON]', canon)
        crafter = production_skills.text('skill-video-prompt-crafter')
        self.assertIn('found_footage', crafter)
        self.assertIn('handheld camera shake', crafter)
        gatekeeper = production_skills.text('skill-cheap-gatekeeper')
        self.assertIn('REJECTED_PRECHECK', gatekeeper)
        self.assertIn('2.5 слов в секунду', gatekeeper)

    def test_routing_contract_registers_production_skills(self):
        entries = {item['id']: item for item in routing()['skills']}
        allowed = {f'N{i:02d}' for i in range(1, 12)} | {'N42'}
        for name in IDS:
            self.assertIn(name, entries)
            entry = entries[name]
            self.assertEqual(entry['kind'], 'repo_existing')
            self.assertTrue((ROOT / entry['repository_path']).is_file(), entry['repository_path'])
            self.assertTrue(entry['used_by'])
            self.assertTrue(set(entry['used_by']).issubset(allowed), entry['used_by'])

    def test_story_plan_system_prompt_includes_strict_json(self):
        from backend import story_plan
        self.assertIn('Strict Schema & Zero Chatter', story_plan.SYSTEM)
        self.assertIn('BLOCKED_INVALID_INPUT', story_plan.SYSTEM)


class NativeChatRules(unittest.TestCase):
    """Подключение скиллов в задании чата (backend/native_chat.py)."""

    class Studio:
        MODEL_SPECS = {'seedance-2.5': {'kind': 'video'}, 'seedream-5-pro': {'kind': 'image'}}

        @staticmethod
        def system_rules(spec):
            return 'БАЗОВЫЕ ПРАВИЛА'

    @staticmethod
    def body(operation, target):
        return SimpleNamespace(operation=operation, target=target)

    def test_video_prompt_attaches_prompt_crafter(self):
        from backend import native_chat
        rules = native_chat.chat_rules(self.Studio(), self.body('prompt', 'seedance-2.5'), {})
        self.assertIn('БАЗОВЫЕ ПРАВИЛА', rules)
        self.assertIn('Technical Video & Image Prompting', rules)

    def test_image_prompt_has_no_prompt_crafter(self):
        from backend import native_chat
        rules = native_chat.chat_rules(self.Studio(), self.body('prompt', 'seedream-5-pro'), {})
        self.assertNotIn('Technical Video & Image Prompting', rules)

    def test_character_description_attaches_canon_lock(self):
        from backend import native_chat
        rules = native_chat.chat_rules(self.Studio(), self.body('describe_character', 'seedream-5-pro'), {})
        self.assertIn('Canon & Character Continuity Lock', rules)

    def test_production_entity_attaches_canon_lock(self):
        from backend import native_chat
        rules = native_chat.chat_rules(self.Studio(), self.body('prompt', 'seedream-5-pro'), {'entity': {'node_id': 'n1'}})
        self.assertIn('Canon & Character Continuity Lock', rules)


class SkillContextS02(unittest.TestCase):
    """Форма S02: skill_context + skills_manifest + выявленные конфликты."""

    def test_context_returns_s02_shape(self):
        packed = production_skills.context(['skill-strict-json-output'])
        self.assertIn('skill_context', packed)
        self.assertIn('skills_manifest', packed)
        self.assertEqual(len(packed['skills_manifest']), 1)
        entry = packed['skills_manifest'][0]
        self.assertEqual(entry['id'], 'skill-strict-json-output')
        raw = (production_skills.SKILLS_ROOT / entry['file']).read_text(encoding='utf-8')
        self.assertEqual(entry['sha256'], production_skills.digest(raw))
        self.assertIn('Strict Schema & Zero Chatter', packed['skill_context'])

    def test_manifest_lists_only_requested_skills(self):
        packed = production_skills.context(['skill-canon-lock'])
        self.assertEqual([entry['id'] for entry in packed['skills_manifest']], ['skill-canon-lock'])

    def test_missing_canon_revision_is_reported_not_fatal(self):
        problems = production_skills.detect_conflicts(['skill-canon-lock'])
        self.assertEqual([item['kind'] for item in problems], ['missing_canon_revision'])
        self.assertEqual(production_skills.detect_conflicts(['skill-canon-lock'], 'rev-1'), [])

    def test_scope_overlap_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = []
            for name in ('skill-a', 'skill-b'):
                (root / name).mkdir()
                body = f'текст {name}'
                (root / name / 'SKILL.md').write_text(body, encoding='utf-8')
                entries.append({'id': name, 'file': f'{name}/SKILL.md',
                                'sha256': production_skills.digest(body), 'version': '1.0',
                                'scope': 'every_llm_system_prompt'})
            (root / 'registry.json').write_text(json.dumps({'skills': entries}), encoding='utf-8')
            with mock.patch.object(production_skills, 'SKILLS_ROOT', root), \
                 mock.patch.object(production_skills, 'REGISTRY_PATH', root / 'registry.json'), \
                 mock.patch.dict(production_skills._cache, {}, clear=True):
                problems = production_skills.detect_conflicts(['skill-a', 'skill-b'])
                self.assertEqual([item['kind'] for item in problems], ['scope_overlap'])

    def test_chat_rules_blocks_scope_overlap(self):
        from fastapi import HTTPException
        from backend import native_chat
        conflict = {'skill_context': '', 'skills_manifest': [],
                    'conflicts': [{'kind': 'scope_overlap', 'skills': ['a', 'b'], 'detail': 'один scope'}]}
        with mock.patch.object(production_skills, 'context', return_value=conflict):
            with self.assertRaises(HTTPException) as caught:
                native_chat.chat_rules(NativeChatRules.Studio(), NativeChatRules.body('prompt', 'seedance-2.5'), {})
        self.assertEqual(caught.exception.status_code, 409)


if __name__ == '__main__':
    unittest.main()
