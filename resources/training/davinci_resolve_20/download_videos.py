#!/usr/bin/env python3
"""Download official Blackmagic DaVinci Resolve training-video ZIPs to local disk.

Only ZIP archives are downloaded by default. Existing verified archives are skipped.
Run from anywhere; output paths are relative to this script, not the current folder.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "video_catalog.json"
DEST = ROOT / "downloaded" / "Training_Videos_ZIP"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".mts", ".m2ts", ".wmv"}
SECTIONS = ("Edit", "Color", "Fairlight", "Fusion")


def is_valid_zip(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0 and zipfile.is_zipfile(path)


def download(url: str, target: Path, force: bool = False) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not force and is_valid_zip(target):
        print(f"  Уже загружен: {target.name}")
        return "cached"
    if target.exists():
        target.unlink()
    partial = target.with_name(target.name + ".part")
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("Не найден curl.exe (поставляется с Windows 10/11).")

    def transfer(resume: bool) -> subprocess.CompletedProcess:
        cmd = [curl, "--fail", "--location", "--show-error", "--progress-bar",
               "--retry", "4", "--retry-delay", "5", "--connect-timeout", "30",
               "--referer", "https://www.blackmagicdesign.com/products/davinciresolve/training",
               "--output", str(partial)]
        if resume:
            cmd += ["--continue-at", "-"]
        return subprocess.run([*cmd, url], check=False)

    print(f"  Загружаю: {target.name}", flush=True)
    response = transfer(resume=True)
    if response.returncode != 0:
        if is_valid_zip(partial):
            # Resume can return HTTP 416 when a previously completed file only
            # needs to be renamed after interruption.
            print("  Частичный файл уже оказался полным ZIP-архивом")
        elif response.returncode == 33:
            print("  Сервер не поддерживает дозагрузку, начну этот архив заново")
            partial.unlink(missing_ok=True)
            response = transfer(resume=False)
        if response.returncode != 0 and not is_valid_zip(partial):
            raise RuntimeError(f"curl: код {response.returncode}; .part сохранён для следующей попытки")
    if not is_valid_zip(partial):
        raise RuntimeError("Полученный файл не является целым ZIP-архивом; .part оставлен для диагностики")
    os.replace(partial, target)
    return "downloaded"


def extract_videos(archive: Path, target: Path) -> int:
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    count = 0
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if info.is_dir() or Path(info.filename).suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            # Reject absolute paths, traversal, platform-specific paths and symlinks.
            parts = info.filename.replace("\\", "/").split("/")
            if any(p in ("", ".", "..") or ":" in p for p in parts) or parts[0].startswith("/"):
                continue
            unix_file_type = (info.external_attr >> 16) & 0o170000
            if unix_file_type == 0o120000:
                continue
            path = root.joinpath(*parts).resolve()
            if not path.is_relative_to(root):
                continue
            if path.is_file() and path.stat().st_size == info.file_size:
                count += 1
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            part = path.with_name(path.name + ".part")
            try:
                with z.open(info) as source, part.open("wb") as dest:
                    shutil.copyfileobj(source, dest, 1024 * 1024)
                os.replace(part, path)
            finally:
                part.unlink(missing_ok=True)
            count += 1
    return count


def remote_zip_size(url: str) -> int | None:
    """Try HEAD to read Content-Length without transferring the ZIP body."""
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        return None
    try:
        response = subprocess.run(
            [curl, "--head", "--location", "--silent", "--show-error",
             "--retry", "1", "--connect-timeout", "10", "--max-time", "25", url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=35,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if response.returncode:
        return None
    # With redirects/proxies there may be multiple HTTP header blocks; read the final one.
    blocks = re.split(rb"\r?\n\r?\n", response.stdout)
    for block in reversed(blocks):
        lines = block.decode("latin-1", errors="replace").splitlines()
        if not lines or not re.match(r"^HTTP/\S+\s+2\d\d(?:\s|$)", lines[0]):
            continue
        for line in lines[1:]:
            m = re.match(r"(?i)^content-length:\s*(\d+)\s*$", line.strip())
            if m:
                return int(m.group(1))
    return None


def show_sizes(entries: list[dict]) -> int:
    print("Проверяю размеры по HTTP-заголовкам (ZIP НЕ скачиваются).\n")
    with ThreadPoolExecutor(max_workers=4) as pool:
        sizes = list(pool.map(lambda item: remote_zip_size(item["url"]), entries))
    known_total = 0
    unknown = 0
    for item, size in zip(entries, sizes):
        if size is None:
            unknown += 1
            description = "размер не предоставлен сервером"
        else:
            known_total += size
            description = f"{size / (1024 ** 3):.2f} ГиБ ({size:,} байт)"
        print(f"[{item['section']}] {item['title']}: {description}")
    print(f"\nИзвестный суммарный объём: {known_total / (1024 ** 3):.2f} ГиБ")
    if unknown:
        print(f"Нет размера для {unknown} из {len(entries)} файлов; полный объём неизвестен.")
    else:
        print("Точный общий объём по текущим HTTP-заголовкам получен.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", choices=SECTIONS, action="append",
                        help="Скачать только выбранную категорию (можно повторить)")
    parser.add_argument("--list", action="store_true", help="Показать список, ничего не скачивать")
    parser.add_argument("--sizes", action="store_true", help="Проверить вес архивов без загрузки данных (HEAD)")
    parser.add_argument("--match", action="append", metavar="TEXT", help="Скачать лишь видео, где название содержит TEXT; можно повторить")
    parser.add_argument("--extract", action="store_true", help="Дополнительно извлечь видеофайлы из ZIP")
    parser.add_argument("--force", action="store_true", help="Перекачать существующие ZIP")
    args = parser.parse_args()

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    entries = [item for item in catalog["videos"] if not args.section or item["section"] in args.section]
    if args.match:
        terms = [term.casefold().strip() for term in args.match if term.strip()]
        entries = [item for item in entries if any(term in item["title"].casefold() for term in terms)]
    if not entries:
        print("Под выбранные фильтры ничего не найдено.", file=sys.stderr)
        return 2
    print(f"Источник: {catalog['source']}\nАрхивов в выбранных категориях: {len(entries)}")
    if args.list:
        for idx, item in enumerate(entries, 1):
            print(f"{idx:2d}. [{item['section']}] {item['title']}  ({item['filename']})")
        return 0

    if args.sizes:
        return show_sizes(entries)

    results = []
    errors = []
    for idx, item in enumerate(entries, 1):
        target = DEST / item["section"] / item["filename"]
        print(f"\n[{idx}/{len(entries)}] [{item['section']}] {item['title']}")
        try:
            status = download(item["url"], target, force=args.force)
            record = {"section": item["section"], "title": item["title"],
                      "file": str(target.relative_to(ROOT)), "bytes": target.stat().st_size,
                      "status": status, "source_url": item["url"]}
            if args.extract:
                extracted_to = DEST / "Extracted_Videos" / item["section"] / target.stem
                record["video_files_extracted"] = extract_videos(target, extracted_to)
                print(f"  Извлечено видеофайлов: {record['video_files_extracted']}")
            results.append(record)
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            problem = f"{item['title']}: {exc}"
            errors.append(problem)
            print(f"  ОШИБКА: {problem}", file=sys.stderr)

    DEST.mkdir(parents=True, exist_ok=True)
    report = {"catalog_source": catalog["source"], "success": results, "errors": errors}
    (DEST / "download-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nПапка с архивами: {DEST}\nГотово: {len(results)}, ошибок: {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
