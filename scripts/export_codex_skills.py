"""Build a skills-only snapshot. Does not commit, push, install or invoke models."""
import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


CATALOG = {
    'gremovod-screenplay': 'Сценарий, сцены, планы и JSON для доски',
    'cinema-narrative-genre': 'История, конфликт и жанр',
    'cinema-mise-en-scene': 'Постановка и актёрское действие',
    'cinema-camera-work': 'Крупности, ракурсы и движение камеры',
    'cinema-editing': 'Монтаж и непрерывность',
    'cinema-sound-design': 'Речь, музыка и звуковая среда',
    'cinema-visual-structure': 'Визуальная структура по Блоку',
}
DOCS = (
    'WILLIAMS_CHARACTER_ACTING_2026-10-16.md',
    'BLOCK_VISUAL_STORY_2026-10-16.md',
    'SKILLS_PRODUCTION_REFERENCE.md',
)


def build(source, target):
    if target == source or source.is_relative_to(target):
        raise ValueError('Export directory must be separate from the source root')
    files = {}
    for name in CATALOG:
        folder = source / 'skills' / name
        for path in folder.rglob('*'):
            if path.is_file():
                if path.suffix not in {'.md', '.json', '.yaml'}:
                    raise ValueError(f'Unexpected skill file: {path.name}')
                files[path.relative_to(source).as_posix()] = path.read_text(encoding='utf-8')
        entry = files[f'skills/{name}/SKILL.md']
        if not entry.startswith('---\n') or not re.search(r'^name:\s*', entry, re.M) or not re.search(r'^description:\s*', entry, re.M):
            raise ValueError(f'Missing frontmatter: {name}')
    for name in DOCS:
        files[f'docs/{name}'] = (source / 'docs' / name).read_text(encoding='utf-8')
    for path, content in list(files.items()):
        content = content.replace('../../projects/GremoVOD/КИНО_И_ПРОИЗВОДСТВО.md', '../../docs/SKILLS_PRODUCTION_REFERENCE.md')
        if path.endswith('WILLIAMS_CHARACTER_ACTING_2026-10-16.md'):
            content = re.sub(r'Текст ранее извлечён.*?содержание по ней не проверено\.',
                             'Разбор подготовлен по ранее извлечённому тексту предоставленного владельцем PDF. Полный текст и исходные изображения книги в коллекцию не включены.', content, flags=re.S)
        files[path] = content
    rows = '\n'.join(f'| [{name}](skills/{name}/SKILL.md) | {topic} | Текст готов; структура и ссылки проверены |' for name, topic in CATALOG.items())
    files['README.md'] = f'''# GremoVOD — скиллы Codex

Ветка `codex/skills` — отдельная коллекция инструкций и справочников. Владелец коллекции: Codex; это не утверждение об авторстве всех исходных материалов. Основной проект: https://github.com/gremoled77-droid/gremovod.

## Что готово

| Скилл | Назначение | Статус |
| --- | --- | --- |
{rows}

«Текст готов» означает, что инструкция составлена. Автоматически проверены обязательные поля заголовка, локальные Markdown-ссылки и JSON. Отдельное испытание каждого скилла в реальной работе Codex не проведено; статус не подтверждает реализацию функций студии.

Уильямс подключён к сценарию и мизансцене, Блок — к визуальной структуре и киноязыку. Папка `docs` содержит авторские выжимки и практические рекомендации, не полные книги. Не копируйте один SKILL.md отдельно от его справочников: относительные ссылки рассчитаны на структуру этой коллекции. Автоматическая установка в Codex не выполнялась.

## Как обновляем

Исходные скиллы редактируются в рабочей ветке проекта. После проверки Codex экспортирует выбранные скиллы командой `python scripts/export_codex_skills.py --target <локальная_копия_ветки_codex_skills>`, просматривает diff, коммитит и отправляет обычным push в `codex/skills`. Перед обновлением получать изменения этой ветки. Force-push не использовать. Это порядок работы по запросу, а не фоновая синхронизация.

При новой версии указывать изменения в сообщении коммита; состав и контрольные суммы находятся в [manifest.json](manifest.json). Рабочие сценарии, проекты постановки, медиа и настройки студии сюда не экспортируются.
'''
    for path, content in files.items():
        if path.endswith('.json'):
            json.loads(content)
        if path.endswith('.md'):
            for link in re.findall(r'\]\(([^)]+)\)', content):
                if '://' in link or link.startswith('#'):
                    continue
                resolved = (target / Path(path).parent / link.split('#')[0]).resolve()
                relative = resolved.relative_to(target).as_posix()
                if relative not in files and relative != 'manifest.json':
                    raise ValueError(f'Broken link: {path} -> {link}')
    expected = set(files) | {'manifest.json'}
    if target.exists():
        actual = {p.relative_to(target).as_posix() for p in target.rglob('*')
                  if p.is_file() and '.git' not in p.relative_to(target).parts}
        if actual - expected:
            raise ValueError(f'Unmanaged files in export: {sorted(actual - expected)}')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    manifest = {'source_commit': revision, 'exported_at': datetime.now(timezone.utc).isoformat(),
                'branch': 'codex/skills', 'skills': list(CATALOG),
                'checks': ['frontmatter-required-fields', 'relative-markdown-links', 'json-parse'],
                'not_checked': ['end-to-end Codex invocation', 'application integration'],
                'files': {p: hashlib.sha256(c.encode('utf-8')).hexdigest() for p, c in files.items()}}
    files['manifest.json'] = json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'
    for path, content in files.items():
        destination = target / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding='utf-8', newline='\n')
    print(f'Exported {len(CATALOG)} skills, {len(files)} files; links and JSON OK')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[1], args.target.resolve())
