"""Загрузка каталога в R2 и манифест того, что залито.

Пример:

    $env:R2_ENDPOINT='https://<account>.r2.cloudflarestorage.com'
    $env:R2_BUCKET='gremovod'
    $env:R2_ACCESS_KEY_ID='...'
    $env:R2_SECRET_ACCESS_KEY='...'
    $env:R2_PUBLIC_BASE_URL='https://assets.grem.win'
    python -m scripts.r2_upload --source C:/Users/BLOWKA/Documents/Minimax/gremovod-site-assets \
        --prefix demo --manifest C:/Users/BLOWKA/Documents/Minimax/r2-manifest.json

Секреты читаются только из окружения и в манифест не попадают."""
import argparse
import hashlib
import json
import mimetypes
import sys
from pathlib import Path

from backend import r2_storage

SKIP_DIRS = {'_args', '__pycache__', '.git', 'node_modules'}


def collect(source, prefix=''):
    """Список файлов для загрузки: (путь, ключ) с ключом вида prefix/относительный/путь."""
    source = Path(source)
    items = []
    for path in sorted(source.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        key = '/'.join([prefix.rstrip('/'), str(relative).replace('\\', '/')]).strip('/')
        items.append((path, key))
    return items


def describe(path, key, url):
    data = path.read_bytes()
    return {
        'key': key,
        'bytes': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
        'content_type': mimetypes.guess_type(str(path))[0] or 'application/octet-stream',
        'url': url,
    }


def build_manifest(cfg, items, prefix, uploaded):
    return {
        'bucket': cfg['bucket'],
        'prefix': prefix,
        'object_count': len(uploaded),
        'total_bytes': sum(item['bytes'] for item in uploaded),
        'objects': uploaded,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Загрузка файлов в R2')
    parser.add_argument('--source', required=True, help='каталог с файлами')
    parser.add_argument('--prefix', default='', help='префикс ключей в бакете')
    parser.add_argument('--manifest', default='', help='куда записать манифест JSON')
    parser.add_argument('--dry-run', action='store_true', help='только показать, что уйдёт')
    parser.add_argument('--include', default='', help='только файлы с этим расширением, например .png')
    args = parser.parse_args(argv)

    cfg = r2_storage.config()
    if not args.dry_run and not r2_storage.enabled(cfg):
        print('R2 не настроен: нужны R2_ENDPOINT, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY',
              file=sys.stderr)
        return 2

    items = collect(args.source, args.prefix)
    if args.include:
        items = [(path, key) for path, key in items if path.suffix.lower() == args.include.lower()]
    uploaded = []
    for path, key in items:
        if args.dry_run:
            print(f'будет загружено: {key} ({path.stat().st_size} байт)')
            continue
        url = r2_storage.put_file(cfg, path, key=key)
        uploaded.append(describe(path, key, url))
        print(f'загружено: {key} -> {url}')

    if not args.dry_run and args.manifest:
        manifest = build_manifest(cfg, items, args.prefix, uploaded)
        Path(args.manifest).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'манифест: {args.manifest} ({manifest["object_count"]} объектов)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
