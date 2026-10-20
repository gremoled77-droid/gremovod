"""Реестр производственных ролей MiniMax: какой набор навыков брать на каком узле.

GitHub — источник истины для текстов навыков: skills/<id>/SKILL.md. Реестр решает
только вопрос «какой набор подключить на узле»; сам платный вызов идёт через
backend/llm_guard.py, где TextTask.skills принимает готовые инструкции.

Модуль ничего не отправляет провайдеру и не тратит бюджет: только чтение файлов.
"""
import hashlib
from pathlib import Path

from fastapi import HTTPException

SKILLS_ROOT = Path(__file__).resolve().parent.parent / 'skills'

# Базовый навык подключается на всех узлах MiniMax.
BASE_SKILL = 'skill-strict-json-output'

# Спецификация контура называет четвёртый навык skill-cheap-gatekeeper.
# Каноническое имя — skill-precheck-filter; прежний идентификатор разрешается.
ALIASES = {'skill-cheap-gatekeeper': 'skill-precheck-filter'}

# Узлы — девять экранов студии (frontend/src/StageNav.tsx).
ROLES = {
    'idea': {'title': 'Идея', 'skills': []},
    'world': {'title': 'Мир', 'skills': ['skill-canon-lock']},
    'chars': {'title': 'Персонажи', 'skills': ['skill-canon-lock']},
    'board': {'title': 'Раскадровка', 'skills': ['skill-canon-lock']},
    'frames': {'title': 'Кадры', 'skills': ['skill-video-prompt-crafter']},
    'video': {'title': 'Видео', 'skills': ['skill-video-prompt-crafter']},
    'sound': {'title': 'Звук', 'skills': []},
    'edit': {'title': 'Монтаж', 'skills': []},
    'release': {'title': 'Выпуск', 'skills': ['skill-evidence-packager']},
}

# Отдельные наборы: ворота перед дорогими критиками и пакет для Media Inspector/QA.
GATE_SKILLS = ['skill-precheck-filter']
EVIDENCE_SKILLS = ['skill-evidence-packager']


def canonical_id(skill_id: str) -> str:
    """Приводит идентификатор навыка к каноническому имени."""
    return ALIASES.get(skill_id, skill_id)


def skill_path(skill_id: str) -> Path:
    return SKILLS_ROOT / canonical_id(skill_id) / 'SKILL.md'


def _strip_frontmatter(text: str) -> str:
    """Отделяет YAML-заголовок от текста инструкции."""
    if not text.startswith('---'):
        return text.strip()
    end = text.find('\n---', 3)
    if end < 0:
        return text.strip()
    return text[end + 4:].strip()


def _title(instructions: str) -> str:
    for line in instructions.splitlines():
        if line.startswith('# '):
            return line[2:].strip()
    return ''


def load_skill(skill_id: str) -> dict:
    """Текст инструкции навыка и версия по содержимому. Нет файла — пустой текст."""
    try:
        raw = skill_path(skill_id).read_text(encoding='utf-8')
    except OSError:
        raw = ''
    instructions = _strip_frontmatter(raw)
    return {'id': canonical_id(skill_id), 'title': _title(instructions), 'instructions': instructions,
            'version': hashlib.sha256(instructions.encode('utf-8')).hexdigest()[:12],
            'available': bool(instructions.strip())}


def _pack(skill_ids) -> list[dict]:
    """Готовый набор для TextTask.skills. Навык без файла пропускается, а не роняет набор."""
    out = []
    for skill_id in skill_ids:
        skill = load_skill(skill_id)
        if not skill['available']:
            continue
        entry = {'id': skill['id'], 'instructions': skill['instructions']}
        if entry not in out:
            out.append(entry)
    return out


def stage_skills(stage_id: str) -> list[dict]:
    """Набор навыков узла: базовый плюс узловые."""
    role = ROLES.get(stage_id)
    if role is None:
        raise HTTPException(400, f'Неизвестный узел студии: {stage_id}. Доступны: {", ".join(ROLES)}')
    return _pack([BASE_SKILL] + role['skills'])


def gate_skills() -> list[dict]:
    """Ворота перед дорогими критиками A6–A8."""
    return _pack([BASE_SKILL] + GATE_SKILLS)


def evidence_skills() -> list[dict]:
    """Пакет технических данных для Media Inspector и QA-контура."""
    return _pack([BASE_SKILL] + EVIDENCE_SKILLS)


def missing_skills() -> list[str]:
    """Навыки реестра, файла которых нет в репозитории."""
    ids = {BASE_SKILL} | {item for role in ROLES.values() for item in role['skills']}
    ids |= set(GATE_SKILLS) | set(EVIDENCE_SKILLS)
    return sorted(skill_id for skill_id in ids if not load_skill(skill_id)['available'])


def registry() -> dict:
    """Снимок реестра: узлы, наборы навыков и недостающие файлы."""
    stages = {}
    for stage_id, role in ROLES.items():
        stages[stage_id] = {'title': role['title'],
                            'skills': [load_skill(item['id']) for item in stage_skills(stage_id)]}
    return {'base_skill': BASE_SKILL, 'stages': stages,
            'gate': gate_skills(), 'evidence': evidence_skills(),
            'missing_skills': missing_skills()}


def register(app, studio):
    @app.get('/api/llm/roles')
    def roles(stage: str | None = None):
        """Реестр ролей MiniMax: набор навыков на узел. Без платных вызовов."""
        if stage:
            return {'stage': stage, 'skills': stage_skills(stage)}
        return registry()
