"""Производственные скиллы бэкенда: целостность реестра, сборка промпта, договорённости.

Проверки бесплатные: ни одного сетевого вызова, ни одного платного API.
"""
import json
import posixpath
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from backend import production_skills

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'docs/specs/n8n-production-2026-10-19/contracts/scenario-skills-routing-v1.json'
IDS = ['skill-strict-json-output', 'skill-canon-lock', 'skill-video-prompt-crafter', 'skill-cheap-gatekeeper',
       'skill-evidence-packager']
SCENARIO_IDS = ['skill-strict-json-output', 'skill-canon-lock', 'skill-video-prompt-crafter', 'skill-cheap-gatekeeper']
SCREENS = ['studio', 'styles', 'characters', 'storyboard', 'create', 'video', 'audio', 'files', 'economics']
LLM_ENGINES = {'BOUNDED_LLM', 'CREATIVE_LLM', 'DIRECTOR_LLM', 'BOUNDED_LLM_AND_CODE', 'RESEARCH_ON_DEMAND'}


def routing():
    return json.loads(CONTRACT.read_text(encoding='utf-8'))


class ProductionSkillsRegistry(unittest.TestCase):
    def test_registry_lists_five_skills(self):
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
        self.assertIn('детализировать действие', canon)
        crafter = production_skills.text('skill-video-prompt-crafter')
        self.assertIn('found_footage', crafter)
        self.assertIn('handheld camera shake', crafter)
        gatekeeper = production_skills.text('skill-cheap-gatekeeper')
        self.assertIn('REJECTED_PRECHECK', gatekeeper)
        self.assertIn('2.5 слов в секунду', gatekeeper)
        packager = production_skills.text('skill-evidence-packager')
        self.assertIn('PASS_TECHNICAL', packager)
        self.assertIn('unmeasured', packager)
        self.assertIn('coverage', packager)

    def test_routing_contract_registers_production_skills(self):
        entries = {item['id']: item for item in routing()['skills']}
        allowed = {f'N{i:02d}' for i in range(1, 12)} | {'N42'}
        for name in SCENARIO_IDS:
            self.assertIn(name, entries)
            entry = entries[name]
            self.assertEqual(entry['kind'], 'repo_existing')
            self.assertTrue((ROOT / entry['repository_path']).is_file(), entry['repository_path'])
            self.assertTrue(entry['used_by'])
            self.assertTrue(set(entry['used_by']).issubset(allowed), entry['used_by'])

    def test_registry_stages_match_contract_used_by(self):
        entries = {item['id']: item for item in routing()['skills']}
        for name in SCENARIO_IDS:
            stages = [item['stages'] for item in production_skills.registry()['skills'] if item['id'] == name][0]
            self.assertEqual(sorted(stages), sorted(entries[name]['used_by']), name)

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


class SkillSyncCompatibility(unittest.TestCase):
    """Совместимость с scripts/n8n_skill_sync.py: пакет = `skills/<имя>/SKILL.md`, без вложенности.

    Правила взяты из инструмента синка: имя по regex `[a-z0-9][a-z0-9-]{0,99}`, frontmatter
    только однострочные `name`/`description`, `name` совпадает с каталогом, а каждая
    относительная md-ссылка должна разрешаться в существующий файл.
    """

    def test_production_skills_are_flat_in_skills_dir(self):
        for name in IDS:
            self.assertTrue((ROOT / 'skills' / name / 'SKILL.md').is_file(), name)

    def test_registry_points_to_repo_skills_root(self):
        self.assertEqual(production_skills.SKILLS_ROOT, ROOT / 'skills')

    def test_skill_names_match_sync_regex(self):
        for name in IDS:
            self.assertRegex(name, r'^[a-z0-9][a-z0-9-]{0,99}$')

    def test_frontmatter_is_single_line_name_and_description(self):
        for name in IDS:
            body = (ROOT / 'skills' / name / 'SKILL.md').read_text(encoding='utf-8')
            match = re.match(r'\A---\n(.*?)\n---\n', body, re.S)
            self.assertIsNotNone(match, name)
            fields = {}
            for line in match.group(1).splitlines():
                key, sep, value = line.partition(':')
                self.assertIn(key, {'name', 'description'}, name)
                self.assertTrue(sep, name)
                self.assertTrue(value.strip(), name)
                self.assertNotIn(value.strip()[0], '|>', name)
                fields[key] = value.strip().strip('"\'')
            self.assertEqual(fields.get('name'), name)
            self.assertTrue(fields.get('description'))

    def test_relative_links_resolve_inside_package(self):
        for name in IDS:
            body = (ROOT / 'skills' / name / 'SKILL.md').read_text(encoding='utf-8')
            for link in re.findall(r'\]\(([^)]+)\)', body):
                if '://' in link or link.startswith('#'):
                    continue
                target = posixpath.normpath(posixpath.join(name, link.split('#')[0]))
                self.assertTrue((ROOT / 'skills' / target).is_file(), target)


class SkillRegistryRouting(unittest.TestCase):
    """Алиасы, экраны студии и ворота — всё в одном реестре."""

    def test_alias_resolves_to_canonical_skill(self):
        self.assertEqual(production_skills.canonical('skill-precheck-filter'), 'skill-cheap-gatekeeper')
        self.assertEqual(production_skills.aliases(), {'skill-precheck-filter': 'skill-cheap-gatekeeper'})

    def test_alias_and_canonical_give_the_same_text(self):
        self.assertEqual(production_skills.text('skill-precheck-filter'),
                         production_skills.text('skill-cheap-gatekeeper'))

    def test_bundle_folds_alias_into_canonical(self):
        self.assertEqual(production_skills.bundle(['skill-precheck-filter', 'skill-cheap-gatekeeper']),
                         ['skill-cheap-gatekeeper'])

    def test_base_skill_is_strict_json(self):
        self.assertEqual(production_skills.base_skill(), 'skill-strict-json-output')

    def test_every_screen_gets_the_base_skill(self):
        for screen in SCREENS:
            self.assertEqual(production_skills.for_screen(screen)[0], 'skill-strict-json-output', screen)

    def test_screen_routing(self):
        screens = production_skills.registry()['screens']
        self.assertEqual(sorted(screens), sorted(SCREENS))
        self.assertIn('skill-canon-lock', production_skills.for_screen('characters'))
        self.assertIn('skill-video-prompt-crafter', production_skills.for_screen('create'))
        self.assertIn('skill-evidence-packager', production_skills.for_screen('economics'))

    def test_gates(self):
        self.assertIn('skill-cheap-gatekeeper', production_skills.for_gate('pre_critics'))
        self.assertIn('skill-evidence-packager', production_skills.for_gate('evidence'))

    def test_unknown_screen_and_gate_are_rejected(self):
        with self.assertRaises(production_skills.SkillError):
            production_skills.for_screen('nope')
        with self.assertRaises(production_skills.SkillError):
            production_skills.for_gate('nope')

    def test_registry_references_only_known_skills(self):
        registry = production_skills.registry()
        known = set(production_skills.available()) | set(production_skills.aliases())
        for screen, item in registry['screens'].items():
            for name in item['skills']:
                self.assertIn(name, known, screen)
        for gate, item in registry['gates'].items():
            for name in item['skills']:
                self.assertIn(name, known, gate)


if __name__ == '__main__':
    unittest.main()
