"""Read-only collision/provenance audit; never runs third-party installers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .validate_manifests import file_hash, identifier, relative_file
except ImportError:
    from validate_manifests import file_hash, identifier, relative_file


def inspect_install(source: Path, destination: Path, names: list[str]) -> dict:
    rows = []
    for name in names:
        identifier(name)
        origin = relative_file(source, name)
        target = relative_file(destination, name)
        row = {'name': name, 'action': 'SKIP_EXISTING' if target.exists() else 'WOULD_COPY',
               'source_available': (origin / 'SKILL.md').is_file(), 'files': {}}
        if origin.is_dir():
            for file in sorted(origin.rglob('*')):
                if file.is_file():
                    # Symlinks/reparse points may not escape the trusted source.
                    checked = relative_file(source, file.relative_to(source).as_posix())
                    row['files'][file.relative_to(origin).as_posix()] = file_hash(checked)
        rows.append(row)
    return {'dry_run': True, 'writes_performed': False, 'skills': rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('names', nargs='+')
    args = parser.parse_args()
    print(json.dumps(inspect_install(args.source, args.destination, args.names), ensure_ascii=False))


if __name__ == '__main__':
    main()
