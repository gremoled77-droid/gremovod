"""Производственные скиллы бэкенда: реестр, проверка целостности, сборка системного промпта.

Реестр (`backend/skills/production/registry.json`) — единственный источник правды о том,
какие тексты и в какие вызовы попадают. Хэш файла сверяется с реестром: расхождение — это
не «работает по-старому», а расхождение версий, поэтому запрос не должен уйти с непроверенным
промптом. Неизвестный скилл, отсутствующий файл и дрейф хэша дают SkillError.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
# Канонические тексты скиллов лежат в общем каталоге репозитория `skills/` — там же, откуда
# их забирает синк в n8n (`scripts/n8n_skill_sync.py` собирает пакет из `skills/<имя>/SKILL.md`).
SKILLS_ROOT = REPO_ROOT / 'skills'
# Реестр — артефакт бэкенда: он перечисляет скиллы, стадии, роли и хэши, но не хранит тексты.
REGISTRY_PATH = ROOT / 'skills' / 'production' / 'registry.json'

_cache = {}


class SkillError(RuntimeError):
    """Реестр или файл скилла недоступны: запрос не должен уйти с непроверенным промптом."""


def _normalise(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')


def digest(text):
    """Хэш содержимого файла с нормализованными переводами строк: CRLF и LF дают одно значение.

    Хэш считается по файлу целиком, а `text()` отдаёт текст без внешних пробелов,
    поэтому хэш `text()` и хэш файла различаются на последнем переводе строки.
    """
    return hashlib.sha256(_normalise(text).encode('utf-8')).hexdigest()


def registry():
    """Разобранный реестр. Кэш: файл реестра меняется только вместе с коммитом."""
    if 'registry' not in _cache:
        try:
            data = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise SkillError(f'Реестр производственных скиллов недоступен: {exc}') from exc
        skills = data.get('skills')
        if not isinstance(skills, list) or not skills:
            raise SkillError('В реестре нет ни одного скилла')
        for item in skills:
            if not isinstance(item, dict):
                raise SkillError('Запись реестра не является объектом')
            for field in ('id', 'file', 'sha256', 'version'):
                if not isinstance(item.get(field), str) or not item[field]:
                    raise SkillError(f'Запись реестра без поля {field}')
        _cache['registry'] = data
    return _cache['registry']


def available():
    """Идентификаторы скиллов в порядке реестра (канонические имена)."""
    return [item['id'] for item in registry()['skills']]


def aliases():
    """Совместимые идентификаторы: алиас → канонический скилл.

    Алиас не создаёт второго текста: он указывает на тот же файл, поэтому в n8n
    и в бэкенде не может оказаться двух расходящихся версий одного скилла.
    """
    return {alias: item['id'] for item in registry()['skills'] for alias in item.get('aliases', [])}


def canonical(name):
    """Приводит идентификатор (в том числе алиас) к каноническому имени."""
    if name in available():
        return name
    alias = aliases().get(name)
    if alias:
        return alias
    raise SkillError(f'Неизвестный производственный скилл: {name}')


def _item(name):
    wanted = canonical(name)
    for item in registry()['skills']:
        if item['id'] == wanted:
            return item
    raise SkillError(f'Неизвестный производственный скилл: {name}')


def text(name):
    """Текст скилла. Хэш файла сверяется с реестром: дрейф — отказ, а не предупреждение."""
    item = _item(name)
    path = SKILLS_ROOT / item['file']
    try:
        body = path.read_text(encoding='utf-8')
    except OSError as exc:
        raise SkillError(f'Файл скилла {name} недоступен: {exc}') from exc
    if digest(body) != item['sha256']:
        raise SkillError(f'Хэш скилла {name} не совпадает с реестром; обнови реестр вместе с файлом')
    return body.strip()


def bundle(names):
    """Скиллы в порядке реестра, без повторов; алиасы сворачиваются в канонические имена."""
    wanted = {canonical(name) for name in (names or ())}
    return [item['id'] for item in registry()['skills'] if item['id'] in wanted]


def system_prompt(base, names):
    """Базовый системный промпт плюс тексты скиллов. Без скиллов база не меняется."""
    parts = [text(name) for name in bundle(names)]
    if not parts:
        return base
    head = (base or '').strip()
    return '\n\n'.join([head, *parts]) if head else '\n\n'.join(parts)


def bundle_hash(names):
    """Хэш комплекта: один и тот же набор даёт одно значение для журнала и проверки версий."""
    source = '\n'.join(f'{name}\n{text(name)}' for name in bundle(names))
    return hashlib.sha256(source.encode('utf-8')).hexdigest()


def for_stage(stage_id):
    """Скиллы, объявленные для стадии сценария (N01–N11, N42)."""
    return [item['id'] for item in registry()['skills'] if stage_id in item.get('stages', [])]


def base_skill():
    """Скилл, подключаемый ко всем вызовам без исключения."""
    name = registry().get('base_skill')
    if not name:
        raise SkillError('В реестре не задан базовый скилл')
    return canonical(name)


def for_screen(screen_id):
    """Набор скиллов экрана студии: базовый плюс экранные."""
    screens = registry().get('screens', {})
    if screen_id not in screens:
        raise SkillError(f'Неизвестный экран студии: {screen_id}. Доступны: ' + ', '.join(sorted(screens)))
    return bundle([base_skill()] + list(screens[screen_id].get('skills', [])))


def for_gate(gate_id):
    """Набор скиллов ворот: базовый плюс скиллы ворот."""
    gates = registry().get('gates', {})
    if gate_id not in gates:
        raise SkillError(f'Неизвестные ворота: {gate_id}. Доступны: ' + ', '.join(sorted(gates)))
    return bundle([base_skill()] + list(gates[gate_id].get('skills', [])))


def for_native_chat(operation, target_kind, has_canon=False):
    """Скиллы для задания владельческого чата (`backend/native_chat.py`).

    Описание персонажа — всегда под замком канона. Промпт для видео-генератора — с правилом
    технического промпта. Маркеры found_footage добавляются только по `prompt_style`, поэтому
    сам скилл подключается безусловно для видео-цели.
    """
    names = []
    if operation == 'describe_character':
        names.append('skill-canon-lock')
    if target_kind == 'video' and operation in {'prompt', 'generate'}:
        names.append('skill-video-prompt-crafter')
    if has_canon and 'skill-canon-lock' not in names:
        names.append('skill-canon-lock')
    return bundle(names)


def detect_conflicts(names, canon_revision=None):
    """Конфликты комплекта по приёмке S02: общий scope и скилл канона без ревизии.

    S02 требует выявлять конфликты до вызова, поэтому проверка возвращает список,
    а не бросает исключение: решение об остановке принимает вызывающий.
    `scope_overlap` — ошибка настройки (два скилла претендуют на одну область);
    `missing_canon_revision` — скилл канона подключён без ревизии.
    """
    problems = []
    scopes = {}
    for name in bundle(names):
        item = _item(name)
        scope = item.get('scope') or ''
        if scope and scope in scopes:
            problems.append({'kind': 'scope_overlap', 'skills': [scopes[scope], name],
                             'detail': f'оба скилла объявляют scope «{scope}»'})
        elif scope:
            scopes[scope] = name
        if item.get('requires_canon') and not canon_revision:
            problems.append({'kind': 'missing_canon_revision', 'skills': [name],
                             'detail': 'скилл канона подключён без canon_revision_id'})
    return problems


def context(names, canon_revision=None):
    """Форма S02: skill_context + skills_manifest.

    skill_context — то, что реально уходит в контекст вызова; skills_manifest — версии,
    хэши и роли подключённых скиллов; conflicts — найденные противоречия комплекта.
    """
    ids = bundle(names)
    manifest = []
    for name in ids:
        item = _item(name)
        manifest.append({'id': name, 'version': item['version'], 'sha256': item['sha256'],
                         'file': item['file'], 'scope': item.get('scope', ''),
                         'stages': item.get('stages', []), 'roles': item.get('roles', []),
                         'requires_canon': bool(item.get('requires_canon'))})
    return {'skill_context': '\n\n'.join(text(name) for name in ids),
            'skills_manifest': manifest,
            'conflicts': detect_conflicts(ids, canon_revision)}
