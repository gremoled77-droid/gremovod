#!/usr/bin/env python3
"""Fetch official Blackmagic training PDFs and Fairlight lesson audio on Windows.

Usage: py -3 resources/training/davinci_resolve_20/download.py
No Python packages required. curl.exe is supplied with modern Windows 10/11.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "catalog.json"
DOWNLOADS = HERE / "downloaded"
AUDIO_EXT = {".wav", ".mp3", ".aif", ".aiff", ".flac", ".ogg", ".m4a", ".wma", ".caf", ".bwf"}


def valid_file(path: Path, kind: str) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    if kind == "pdf":
        with path.open("rb") as f:
            return f.read(5) == b"%PDF-"
    return zipfile.is_zipfile(path)


def fetch(url: str, target: Path, kind: str) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if valid_file(target, kind):
        print(f"  [готово] {target.name}")
        return "cached"
    if target.exists():
        target.unlink()  # invalid final artifact
    partial = target.with_name(target.name + ".part")
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl.exe не найден. Для Windows 10/11 установи curl или обнови Windows.")
    cmd = [curl, "--fail", "--location", "--show-error", "--progress-bar",
           "--retry", "4", "--retry-delay", "3", "--connect-timeout", "30",
           "--user-agent", "Mozilla/5.0 GremoVOD-Training-Downloader",
           "--referer", "https://www.blackmagicdesign.com/products/davinciresolve/training",
           "--continue-at", "-", "--output", str(partial), url]
    print(f"  [скачиваю] {target.name}")
    process = subprocess.run(cmd, check=False)
    if process.returncode == 33 and partial.exists():
        # Origin refused the Range request; retry as a complete download.
        partial.unlink()
        process = subprocess.run([x for x in cmd if x not in ("--continue-at", "-")], check=False)
    if process.returncode:
        raise RuntimeError(f"curl завершился с кодом {process.returncode}; частичный файл сохранён")
    if not valid_file(partial, kind):
        raise RuntimeError(f"Файл {target.name} не похож на {kind.upper()}; проверь URL/доступ")
    partial.replace(target)
    return "downloaded"


def extract_audio(archive: Path, dest: Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    copied = 0
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            if info.is_dir() or Path(info.filename).suffix.lower() not in AUDIO_EXT:
                continue
            # ZIP entries are POSIX-separated even on Windows; block traversal.
            segments = info.filename.replace("\\", "/").split("/")
            if any(seg in ("", ".", "..") or ":" in seg for seg in segments):
                continue
            output = root.joinpath(*segments).resolve()
            if not output.is_relative_to(root):
                continue
            if output.exists() and output.stat().st_size == info.file_size:
                copied += 1
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            temp = output.with_name(output.name + ".part")
            try:
                with bundle.open(info) as src, temp.open("wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                temp.replace(output)
            finally:
                if temp.exists():
                    temp.unlink()
            copied += 1
    return copied


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for piece in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(piece)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--pdf-only", action="store_true", help="только шесть PDF-книг")
    group.add_argument("--audio-only", action="store_true", help="только четыре Fairlight ZIP")
    ap.add_argument("--no-extract", action="store_true", help="не распаковывать аудиофайлы из ZIP")
    ap.add_argument("--remove-zips", action="store_true", help="удалить ZIP после успешного извлечения")
    args = ap.parse_args()
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    jobs = []
    if not args.audio_only:
        jobs += [(item, "pdf", DOWNLOADS / "PDF" / item["filename"]) for item in data["pdf"]]
    if not args.pdf_only:
        jobs += [(item, "zip", DOWNLOADS / "Fairlight_Archives" / item["filename"])
                 for item in data["fairlight_archives"]]
    report = {"source": data["source"], "edition": data["edition"], "files": [], "errors": []}
    for idx, (item, kind, out) in enumerate(jobs, 1):
        print(f"[{idx}/{len(jobs)}] {item['title']}", flush=True)
        try:
            state = fetch(item["url"], out, kind)
            entry = {"title": item["title"], "path": str(out.relative_to(HERE)),
                     "bytes": out.stat().st_size, "sha256": sha256(out), "status": state,
                     "url": item["url"]}
            if kind == "zip" and not args.no_extract:
                n = extract_audio(out, DOWNLOADS / "Fairlight_Audio" / out.stem)
                entry["audio_files_extracted"] = n
                print(f"  [аудио] {n} файлов извлечено")
                if args.remove_zips:
                    if n == 0:
                        print("  [сохранено] ZIP не удалён: внутри не найдено отдельных аудиофайлов")
                    else:
                        out.unlink()
                        entry["archive_removed"] = True
            report["files"].append(entry)
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            message = f"{item['title']}: {exc}"
            print("  [ОШИБКА]", message, file=sys.stderr)
            report["errors"].append(message)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    (DOWNLOADS / "download-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nКаталог: {DOWNLOADS}\nУспешно: {len(report['files'])}; ошибок: {len(report['errors'])}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
