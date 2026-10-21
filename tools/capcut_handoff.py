"""Offline CapCut handoff pack for GremoVOD.

Builds a folder of raw materials plus a montage sheet that a human imports into
CapCut by hand. This is NOT a native CapCut project and does not pretend to be
one: version 1 is a source-material pack with editing instructions.

The shot order comes from an edit-list JSON exported by ``backend/edit_list.py``;
this module never rebuilds that list. Reused from the existing local tool
``tools/mock_media_pilot.py``: SHA-256 hashing, the ffprobe subprocess wrapper
and the synthetic media makers used by the tests. No second mock-media engine.

Safety rules of this module:
* local filesystem only — no network, no paid API, no Studio SQLite;
* the only readable files are inside the explicit ``media_root``;
* the output folder must be separate from the media root and must be empty;
* originals are copied byte-for-byte and never modified.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from tools import mock_media_pilot
except ImportError:  # direct execution: python tools/capcut_handoff.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools import mock_media_pilot

SCHEMA = "gremovod.capcut-handoff/1"
CLIPS_DIR = "01_Clips"
AUDIO_DIR = "02_Audio"
REFERENCES_DIR = "03_References"
EDIT_LIST_CSV = "edit-list.csv"
EDIT_LIST_JSON = "edit-list.json"
MANIFEST_NAME = "manifest.json"
README_NAME = "README_RU.md"
AUDIO_TRACKS = ("voice", "music", "sfx")
VERTICAL_SUFFIX = "_9x16"
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
CSV_HEADER = ["№", "Сцена", "Кадр", "Название", "Файл в пакете", "SHA-256", "Длительность, с",
              "Разрешение", "FPS", "Референс", "Источник"]


class HandoffError(RuntimeError):
    """The pack cannot be built safely."""


# ---------- small helpers ----------

def _issue(code, severity, message, **context):
    entry = {"code": code, "severity": severity, "message": message}
    if context:
        entry["context"] = context
    return entry


def sha256_file(path):
    """SHA-256 of one file, reusing the existing local mock-media helper."""
    return mock_media_pilot.checksum(Path(path))


def copy_file(source, dest):
    """Copy one media file into the pack. Test seam: the export calls this."""
    shutil.copy2(source, dest)


def ffprobe_path():
    """Locate ffprobe: PATH first, then the studio-local ``tools/ffmpeg/bin`` copy."""
    found = shutil.which("ffprobe")
    if found:
        return found
    local = Path(__file__).resolve().parent / "ffmpeg" / "bin" / "ffprobe.exe"
    return str(local) if local.is_file() else None


def _duration(data):
    try:
        return round(float((data.get("format") or {}).get("duration")), 2)
    except (TypeError, ValueError):
        return None


def _fps(stream):
    rate = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
    if not rate or "/" not in str(rate):
        return None
    numerator, _, denominator = str(rate).partition("/")
    try:
        top, bottom = float(numerator), float(denominator)
    except ValueError:
        return None
    return round(top / bottom, 3) if bottom else None


def _aspect(width, height):
    if not width or not height:
        return None
    ratio = width / height
    if abs(ratio - 16 / 9) <= 0.06:
        return "16:9"
    if abs(ratio - 9 / 16) <= 0.06:
        return "9:16"
    return f"{width}x{height}"


def probe_media(path):
    """Duration, resolution and FPS of one media file, or ``None`` when unknown."""
    binary = ffprobe_path()
    if not binary:
        return None
    try:
        raw = mock_media_pilot.invoke([binary, "-v", "error", "-show_format",
                                       "-show_streams", "-of", "json", str(path)])
        data = json.loads(raw)
    except (mock_media_pilot.MockMediaError, OSError, json.JSONDecodeError):
        return None
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if video is None:
        return {"duration_seconds": _duration(data), "width": None, "height": None,
                "fps": None, "aspect_ratio": None, "audio_streams": len(audio)}
    width, height = video.get("width"), video.get("height")
    return {"duration_seconds": _duration(data), "width": width, "height": height,
            "fps": _fps(video), "aspect_ratio": _aspect(width, height),
            "audio_streams": len(audio)}


# ---------- input validation ----------

def resolve_media_path(media_root, relative):
    """Resolve one relative media path inside the allowed root.

    Absolute paths, ``..`` escapes and symlinks that leave the root are refused
    with ``HandoffError`` instead of being silently clipped.
    """
    root = Path(media_root).resolve()
    if not isinstance(relative, str) or not relative.strip():
        raise HandoffError("Путь к файлу в монтажном листе пуст")
    candidate = Path(relative)
    if candidate.is_absolute() or candidate.drive or candidate.root:
        raise HandoffError(f"Абсолютный путь запрещён: {relative}")
    resolved = (root / candidate).resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise HandoffError(f"Путь выходит за разрешённый корень медиа: {relative}")
    return resolved


def read_edit_list(edit_list_path):
    """Read the exported edit-list JSON."""
    path = Path(edit_list_path)
    if not path.is_file():
        raise HandoffError(f"Файл монтажного листа не найден: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffError(f"Монтажный лист не читается: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        raise HandoffError("В монтажном листе нет списка rows")
    return data


def _ordered_rows(rows):
    """Rows in edit-list order: the explicit ``order`` field first, file order otherwise."""
    def key(item):
        index, row = item
        order = row.get("order") if isinstance(row, dict) else None
        return (0, order, index) if isinstance(order, int) else (1, 0, index)
    return [row for _, row in sorted(enumerate(rows), key=key)]


def _normalise_tracks(audio_tracks):
    if not audio_tracks:
        return {}
    if not isinstance(audio_tracks, dict):
        raise HandoffError("Звуковые дорожки должны быть словарём «трек → список файлов»")
    tracks = {}
    for name, value in audio_tracks.items():
        if name not in AUDIO_TRACKS:
            raise HandoffError(f"Неизвестная звуковая дорожка: {name}. "
                               f"Допустимые дорожки: {', '.join(AUDIO_TRACKS)}")
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple)):
            raise HandoffError(f"Дорожка {name}: ожидается список файлов")
        tracks[name] = [str(item) for item in value if str(item).strip()]
    return tracks


def _normalise_verticals(vertical_map):
    if not vertical_map:
        return {}
    if not isinstance(vertical_map, dict):
        raise HandoffError("Карта вертикальных версий должна быть словарём «16:9 → 9:16»")
    return {str(key): str(value) for key, value in vertical_map.items()}


def _number(value, fallback):
    return value if isinstance(value, int) and not isinstance(value, bool) else fallback


def _prepare_output(output_dir, media_root):
    """Create an empty, separate output folder; refuse to touch anything else."""
    target = Path(output_dir)
    resolved = target.resolve()
    if resolved.is_relative_to(media_root) or media_root.is_relative_to(resolved):
        raise HandoffError("Выходная папка не может находиться внутри корня медиа и наоборот")
    if target.exists():
        if not target.is_dir():
            raise HandoffError(f"Выходной путь не является папкой: {target}")
        if any(target.iterdir()):
            raise HandoffError(f"Выходная папка не пуста — отказ от перезаписи: {target}")
    target.mkdir(parents=True, exist_ok=True)


def _pack_name(order, scene, frame, suffix=""):
    return f"{order:03d}_scene{scene:02d}_shot{frame:02d}{suffix}"


def _prepare_folders(target):
    """Create the documented package layout, including the empty audio tracks."""
    for folder in (CLIPS_DIR, REFERENCES_DIR):
        (target / folder).mkdir(parents=True, exist_ok=True)
    for name in AUDIO_TRACKS:
        (target / AUDIO_DIR / name).mkdir(parents=True, exist_ok=True)


def _vertical_sibling(source):
    """The conventional vertical sibling ``<stem>_9x16.<ext>`` next to a 16:9 clip."""
    if source.stem.endswith(VERTICAL_SUFFIX):
        return None
    return source.with_name(source.stem + VERTICAL_SUFFIX + source.suffix)


def _pack_file(source, destination, issues, label):
    """Copy one file into the pack and prove that source and copy agree."""
    before = sha256_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    copy_file(source, destination)
    after_source = sha256_file(source)
    copied = sha256_file(destination)
    size = destination.stat().st_size
    if after_source != before:
        issues.append(_issue("SOURCE_CHANGED_DURING_EXPORT", "blocking",
                             f"{label}: исходный файл изменился во время экспорта",
                             source=str(source), sha256_before=before, sha256_after=after_source))
    if copied != before:
        issues.append(_issue("COPY_MISMATCH", "blocking",
                             f"{label}: копия не совпадает с исходным файлом",
                             source=str(source), sha256_source=before, sha256_copy=copied))
    return {"sha256": copied, "bytes": size}


# ---------- export ----------

def export_handoff(edit_list_path, media_root, output_dir, *, audio_tracks=None, vertical_map=None):
    """Build the CapCut handoff pack and return its manifest.

    ``edit_list_path`` is the JSON exported by ``backend/edit_list.py``;
    ``media_root`` is the only folder whose files may be packed; ``output_dir``
    must be a separate, empty folder. Audio tracks are packed only when they
    are passed explicitly. A 9:16 variant is packed only when the file really
    exists — never fabricated.
    """
    source_list = Path(edit_list_path)
    root = Path(media_root).resolve()
    target = Path(output_dir)
    if not root.is_dir():
        raise HandoffError(f"Корень разрешённых файлов не найден: {root}")
    data = read_edit_list(source_list)
    rows = _ordered_rows(data.get("rows") or [])
    tracks = _normalise_tracks(audio_tracks)
    verticals = _normalise_verticals(vertical_map)

    # Resolve every referenced path BEFORE touching the filesystem: a path that
    # escapes the allowed root must not leave a half-written pack behind.
    plan = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise HandoffError(f"Строка {index + 1} монтажного листа не является объектом")
        order = _number(row.get("order"), index + 1)
        scene = _number(row.get("scene"), order)
        frame = _number(row.get("frame"), order)
        clip_relative = str(row.get("video") or "")
        image_relative = str(row.get("image") or "")
        clip_source = resolve_media_path(root, clip_relative) if clip_relative.strip() else None
        image_source = resolve_media_path(root, image_relative) if image_relative.strip() else None
        vertical_source = None
        if clip_source is not None:
            mapped = verticals.get(clip_relative)
            if mapped:
                vertical_source = resolve_media_path(root, mapped)
            else:
                candidate = _vertical_sibling(clip_source)
                if candidate is not None and candidate.is_file():
                    vertical_source = candidate
        plan.append({"order": order, "scene": scene, "frame": frame, "row": row,
                     "clip_relative": clip_relative, "clip_source": clip_source,
                     "image_relative": image_relative, "image_source": image_source,
                     "vertical_source": vertical_source})
    track_plan = {}
    for name, relatives in tracks.items():
        track_plan[name] = [(relative, resolve_media_path(root, relative)) for relative in relatives]

    _prepare_output(target, root)
    _prepare_folders(target)

    issues = []
    clips, references = [], []
    audio_entries = {name: [] for name in AUDIO_TRACKS}
    files = []
    sheet = []
    taken_names = set()
    source_usage = {}

    for item in plan:
        row = item["row"]
        stem = _pack_name(item["order"], item["scene"], item["frame"])
        clip_source = item["clip_source"]
        clip_entry = {"order": item["order"], "scene": item["scene"], "frame": item["frame"],
                      "title": row.get("title") or "", "source": item["clip_relative"],
                      "path": None, "sha256": None, "bytes": None, "media": None,
                      "variant_9x16": None}
        if clip_source is None:
            issues.append(_issue("MISSING_CLIP", "blocking",
                                 f"Кадр {item['order']}: в монтажном листе нет выбранного видео",
                                 order=item["order"], scene=item["scene"], frame=item["frame"]))
        elif not clip_source.is_file():
            issues.append(_issue("MISSING_CLIP", "blocking",
                                 f"Кадр {item['order']}: файл клипа отсутствует: {item['clip_relative']}",
                                 order=item["order"], source=item["clip_relative"]))
        elif clip_source.suffix.lower() not in VIDEO_SUFFIXES:
            issues.append(_issue("UNSUPPORTED_MEDIA", "blocking",
                                 f"Кадр {item['order']}: не видеофайл: {item['clip_relative']}",
                                 order=item["order"], source=item["clip_relative"]))
        else:
            name = stem + clip_source.suffix.lower()
            if name in taken_names:
                issues.append(_issue("DUPLICATE_DESTINATION_NAME", "blocking",
                                     f"Кадр {item['order']}: имя {name} уже занято в пакете — файл не скопирован",
                                     order=item["order"], name=name))
            else:
                taken_names.add(name)
                destination = target / CLIPS_DIR / name
                packed = _pack_file(clip_source, destination, issues,
                                    f"Кадр {item['order']} ({item['clip_relative']})")
                clip_entry["path"] = f"{CLIPS_DIR}/{name}"
                clip_entry["sha256"] = packed["sha256"]
                clip_entry["bytes"] = packed["bytes"]
                clip_entry["media"] = probe_media(destination)
                files.append({"path": clip_entry["path"], "sha256": packed["sha256"],
                              "bytes": packed["bytes"], "role": "clip"})
                usage = source_usage.setdefault(item["clip_relative"], item["order"])
                if usage != item["order"]:
                    issues.append(_issue("DUPLICATE_SOURCE", "warning",
                                         f"Кадр {item['order']}: тот же исходный файл, что и кадр {usage}: "
                                         f"{item['clip_relative']}",
                                         order=item["order"], source=item["clip_relative"]))
        vertical_source = item["vertical_source"]
        if vertical_source is not None and clip_entry["path"] is not None:
            if not vertical_source.is_file():
                issues.append(_issue("MISSING_VERTICAL", "warning",
                                     f"Кадр {item['order']}: вертикальная версия не найдена: {vertical_source}",
                                     order=item["order"]))
            else:
                name = stem + VERTICAL_SUFFIX + vertical_source.suffix.lower()
                if name in taken_names:
                    issues.append(_issue("DUPLICATE_DESTINATION_NAME", "blocking",
                                         f"Кадр {item['order']}: имя {name} уже занято в пакете — файл не скопирован",
                                         order=item["order"], name=name))
                else:
                    taken_names.add(name)
                    destination = target / CLIPS_DIR / name
                    packed = _pack_file(vertical_source, destination, issues,
                                        f"Кадр {item['order']} 9:16 ({vertical_source.name})")
                    clip_entry["variant_9x16"] = f"{CLIPS_DIR}/{name}"
                    files.append({"path": clip_entry["variant_9x16"], "sha256": packed["sha256"],
                                  "bytes": packed["bytes"], "role": "clip_9x16"})
        image_source = item["image_source"]
        reference_entry = None
        if image_source is not None:
            if not image_source.is_file():
                issues.append(_issue("MISSING_REFERENCE", "warning",
                                     f"Кадр {item['order']}: референс не найден: {item['image_relative']}",
                                     order=item["order"], source=item["image_relative"]))
            elif image_source.suffix.lower() not in IMAGE_SUFFIXES:
                issues.append(_issue("UNSUPPORTED_MEDIA", "warning",
                                     f"Кадр {item['order']}: референс не является изображением: "
                                     f"{item['image_relative']}", order=item["order"]))
            else:
                name = stem + image_source.suffix.lower()
                if name in taken_names:
                    issues.append(_issue("DUPLICATE_DESTINATION_NAME", "blocking",
                                         f"Кадр {item['order']}: имя {name} уже занято в пакете — файл не скопирован",
                                         order=item["order"], name=name))
                else:
                    taken_names.add(name)
                    destination = target / REFERENCES_DIR / name
                    packed = _pack_file(image_source, destination, issues,
                                        f"Референс кадра {item['order']} ({item['image_relative']})")
                    reference_entry = {"source": item["image_relative"],
                                       "path": f"{REFERENCES_DIR}/{name}",
                                       "sha256": packed["sha256"], "bytes": packed["bytes"]}
                    references.append(reference_entry)
                    files.append({"path": reference_entry["path"], "sha256": packed["sha256"],
                                  "bytes": packed["bytes"], "role": "reference"})
        clips.append(clip_entry)
        media = clip_entry["media"] or {}
        sheet.append({"order": item["order"], "scene": item["scene"], "frame": item["frame"],
                      "title": row.get("title") or "", "clip": clip_entry["path"] or "",
                      "sha256": clip_entry["sha256"] or "",
                      "duration_seconds": media.get("duration_seconds"),
                      "width": media.get("width"), "height": media.get("height"),
                      "fps": media.get("fps"), "aspect_ratio": media.get("aspect_ratio"),
                      "reference": reference_entry["path"] if reference_entry else "",
                      "source": item["clip_relative"]})

    for name, entries in track_plan.items():
        for relative, source_path in entries:
            if not source_path.is_file():
                issues.append(_issue("MISSING_AUDIO", "blocking",
                                     f"Звуковая дорожка {name}: файл отсутствует: {relative}",
                                     track=name, source=relative))
                continue
            if source_path.suffix.lower() not in AUDIO_SUFFIXES:
                issues.append(_issue("UNSUPPORTED_MEDIA", "blocking",
                                     f"Звуковая дорожка {name}: не звуковой файл: {relative}",
                                     track=name, source=relative))
                continue
            file_name = source_path.name
            if file_name in taken_names:
                issues.append(_issue("DUPLICATE_DESTINATION_NAME", "blocking",
                                     f"Звуковая дорожка {name}: имя {file_name} уже занято в пакете — файл не скопирован",
                                     track=name, name=file_name))
                continue
            taken_names.add(file_name)
            destination = target / AUDIO_DIR / name / file_name
            packed = _pack_file(source_path, destination, issues,
                                f"Звук {name} ({relative})")
            entry = {"source": relative, "path": f"{AUDIO_DIR}/{name}/{file_name}",
                     "sha256": packed["sha256"], "bytes": packed["bytes"]}
            audio_entries[name].append(entry)
            files.append({"path": entry["path"], "sha256": packed["sha256"],
                          "bytes": packed["bytes"], "role": f"audio_{name}"})

    blocking = [i for i in issues if i["severity"] == "blocking"]
    manifest = {
        "schema": SCHEMA,
        "status": "INCOMPLETE" if blocking else "READY_FOR_MONTAGE",
        "ready_for_montage": not blocking,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {
            "edit_list": str(source_list.resolve()),
            "edit_list_sha256": sha256_file(source_list),
            "media_root": str(root),
            "edit_list_warnings": data.get("warnings") or [],
        },
        "counts": {
            "clips": sum(1 for c in clips if c["path"]),
            "vertical": sum(1 for c in clips if c["variant_9x16"]),
            "audio": sum(len(v) for v in audio_entries.values()),
            "references": len(references),
            "blocking_issues": len(blocking),
        },
        "clips": clips,
        "audio_tracks": audio_entries,
        "references": references,
        "files": files,
        "issues": issues,
        "documents": [],
        "limits": {
            "native_capcut_project": False,
            "note": "Пакет исходных материалов и монтажных инструкций, не импортируемый проект CapCut",
            "paid_api_calls": 0,
            "studio_sqlite_accessed": False,
            "network_accessed": False,
        },
    }

    _write_sheet(target, sheet)
    _write_json(target / EDIT_LIST_JSON, {
        "schema": SCHEMA,
        "generated_at": manifest["generated_at"],
        "source_edit_list": str(source_list.resolve()),
        "rows": sheet,
    })
    _write_text(target / README_NAME, _readme(manifest, sheet))
    manifest["documents"] = [
        {"path": name, "sha256": sha256_file(target / name), "bytes": (target / name).stat().st_size}
        for name in (EDIT_LIST_CSV, EDIT_LIST_JSON, README_NAME)
    ]
    _write_json(target / MANIFEST_NAME, manifest)
    return manifest


def _write_sheet(target, rows):
    path = target / EDIT_LIST_CSV
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(CSV_HEADER)
        for row in rows:
            resolution = f"{row['width']}x{row['height']}" if row["width"] and row["height"] else ""
            writer.writerow([row["order"], row["scene"], row["frame"], row["title"], row["clip"],
                             row["sha256"], "" if row["duration_seconds"] is None else row["duration_seconds"],
                             resolution, "" if row["fps"] is None else row["fps"], row["reference"],
                             row["source"]])


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path, text):
    path.write_text(text, encoding="utf-8")


def _readme(manifest, rows):
    counts = manifest["counts"]
    lines = [
        "# Пакет материалов для CapCut",
        "",
        f"- Статус: **{manifest['status']}**",
        f"- Готов к монтажу: {'да' if manifest['ready_for_montage'] else 'нет'}",
        f"- Собрано: {manifest['generated_at']}",
        f"- Клипов: {counts['clips']} (версий 9:16: {counts['vertical']}), "
        f"звуковых файлов: {counts['audio']}, референсов: {counts['references']}",
        "",
        "## Как импортировать",
        "",
        "1. Создай новый проект 16:9 в CapCut.",
        "2. Импортируй все файлы из `01_Clips` — их имена уже задают порядок: "
        "`NNN_sceneNN_shotNN` (номер, сцена, кадр).",
        "3. Звуковые дорожки импортируй отдельно из `02_Audio/voice`, `02_Audio/music`, "
        "`02_Audio/sfx` и положи каждую на свою дорожку.",
        "4. Изображения из `03_References` используй как референсы кадра.",
        "5. Порядок, длительности, разрешение и FPS каждого кадра — в `edit-list.csv` "
        "и `edit-list.json`; контрольные суммы файлов — в `manifest.json`.",
        "",
        "## Порядок монтажа",
        "",
        "| № | Сцена | Кадр | Файл | Длительность, с | Разрешение | FPS | Референс |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        resolution = f"{row['width']}x{row['height']}" if row["width"] and row["height"] else ""
        lines.append(f"| {row['order']} | {row['scene']} | {row['frame']} | `{row['clip']}` | "
                     f"{'' if row['duration_seconds'] is None else row['duration_seconds']} | "
                     f"{resolution} | {'' if row['fps'] is None else row['fps']} | "
                     f"{row['reference'] or '—'} |")
    lines += ["", "## Звуковые дорожки", ""]
    for name, entries in manifest["audio_tracks"].items():
        if entries:
            lines.append(f"- **{name}**: " + ", ".join(f"`{e['path']}`" for e in entries))
        else:
            lines.append(f"- **{name}**: файлов нет")
    lines += ["", "## Замечания экспорта", ""]
    if manifest["issues"]:
        lines.append("| Уровень | Код | Сообщение |")
        lines.append("|---|---|---|")
        for issue in manifest["issues"]:
            lines.append(f"| {issue['severity']} | {issue['code']} | {issue['message']} |")
        blocking = manifest["counts"]["blocking_issues"]
        lines += ["", f"Блокирующих замечаний: **{blocking}**. Пока они есть, пакет "
                      f"не считается готовым к монтажу."]
    else:
        lines.append("Замечаний нет.")
    lines += [
        "",
        "## Ограничения версии 1",
        "",
        "- Это пакет исходных материалов и инструкций, а не импортируемый проект CapCut.",
        "- 9:16 версии включаются только тогда, когда такой файл реально существует; "
        "версия 9:16 не создаётся и не имитируется.",
        "- Проверка целостности: `python -X utf8 -m tools.capcut_handoff "
        "--edit-list <лист> --media-root <корень> --output <папка>` и "
        "`verify_package(<папка>)`.",
        "- Оригиналы не изменяются: в пакет попадают побайтовые копии с SHA-256.",
        "",
    ]
    return "\n".join(lines)


# ---------- verification ----------

def verify_package(output_dir):
    """Re-read a finished pack and check it against its own manifest."""
    target = Path(output_dir)
    manifest_path = target / MANIFEST_NAME
    if not manifest_path.is_file():
        raise HandoffError(f"Манифест пакета не найден: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffError(f"Манифест пакета не читается: {exc}") from exc
    mismatches = []
    checked = 0
    for entry in list(manifest.get("files") or []) + list(manifest.get("documents") or []):
        relative = entry.get("path")
        if not relative:
            mismatches.append("запись манифеста без пути")
            continue
        checked += 1
        path = target / relative
        if not path.is_file():
            mismatches.append(f"{relative}: файл отсутствует")
            continue
        if sha256_file(path) != entry.get("sha256"):
            mismatches.append(f"{relative}: SHA-256 не совпадает с манифестом")
        size = entry.get("bytes")
        if size is not None and path.stat().st_size != size:
            mismatches.append(f"{relative}: размер не совпадает с манифестом")
    return {"ok": not mismatches, "checked": checked, "mismatches": mismatches,
            "status": manifest.get("status"), "ready_for_montage": manifest.get("ready_for_montage")}


# ---------- command line ----------

def main(argv=None):
    parser = argparse.ArgumentParser(description="Сборка пакета материалов для CapCut (офлайн).")
    parser.add_argument("--edit-list", required=True, help="JSON монтажного листа (export edit-list)")
    parser.add_argument("--media-root", required=True, help="Папка, из которой разрешено брать файлы")
    parser.add_argument("--output", required=True, help="Пустая выходная папка пакета")
    parser.add_argument("--audio", action="append", default=[], metavar="TRACK:FILES",
                        help="Звуковая дорожка, файлы через запятую: voice:a.wav,b.wav")
    parser.add_argument("--vertical", action="append", default=[], metavar="SRC=DST",
                        help="Явная пара 16:9 → 9:16 внутри корня медиа")
    args = parser.parse_args(argv)
    tracks = {}
    for item in args.audio:
        name, separator, files = item.partition(":")
        if not separator:
            parser.error(f"--audio ожидает TRACK:FILES, получено {item!r}")
        tracks[name] = [part for part in files.split(",") if part.strip()]
    verticals = {}
    for item in args.vertical:
        source, separator, destination = item.partition("=")
        if not separator:
            parser.error(f"--vertical ожидает SRC=DST, получено {item!r}")
        verticals[source] = destination
    try:
        manifest = export_handoff(args.edit_list, args.media_root, args.output,
                                  audio_tracks=tracks or None, vertical_map=verticals or None)
    except HandoffError as exc:
        print(f"ОТКАЗ: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["ready_for_montage"] else 1


if __name__ == "__main__":
    sys.exit(main())
