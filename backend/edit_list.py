"""Edit list for CapCut (order of shots, files, durations, cut contrast), 9:16 recompose prompt and project-level rules text."""
import csv
import io
import json
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from backend import frame_analysis, production_folders as folders, visual_plan

LONG_SHOT_SECONDS = 10
VERTICAL_RULES = (
    'VERTICAL 9:16 VERSION. Recompose this shot for a portrait frame; do not crop or stretch the 16:9 frame. '
    'Same characters, location, props, costume and palette as the approved reference. '
    'Stack subject and context vertically instead of spreading them sideways: key subject and eyes in the upper-middle third, '
    'keep the top 10% and bottom 20% free of important detail (platform interface). '
    'Separate layers by size, tone and saturated colour; use pillars, mirror and window frames as vertical dividers. '
    'No wide empty side areas, no reliance on subtle left-right attention shifts.'
)
SPACE_VERTICAL = {
    'deep': 'Keep depth as layers from bottom foreground to top background, with strong size difference between layers.',
    'flat': 'Keep one frontal plane, subjects stacked at the same distance, limited tonal range.',
    'limited': 'Keep two or three frontal layers stacked vertically, no receding lines.',
    'ambiguous': 'Keep the scale ambiguous but place the readable focal point in the upper-middle third.',
}


def ffprobe_path(studio):
    found = shutil.which('ffprobe')
    if found:
        return found
    local = Path(studio.ROOT).parent / 'tools' / 'ffmpeg' / 'bin' / 'ffprobe.exe'
    return str(local) if local.is_file() else None


def duration(studio, path):
    probe = ffprobe_path(studio)
    if not probe:
        return None
    try:
        out = subprocess.run([probe, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
                             capture_output=True, text=True, timeout=15)
        return round(float(out.stdout.strip()), 2)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def score(parts):
    """0..1 summary of how visibly one shot differs from the next."""
    return round((min(1, parts['tone']) + min(1, parts['saturation'] * 2) + min(1, parts['warmth']) + parts['lines'] + parts['sector']) / 5, 3)


def label(value):
    return 'гладкая' if value < 0.25 else ('заметная' if value < 0.5 else 'резкая')


def choose(items, chosen):
    """main = выбран владельцем; candidate = выбора нет (или он устарел), взят последний дубль; none = файлов нет.
    items упорядочены от новых к старым."""
    main = next((dict(f) for f in items if f['id'] == chosen), None)
    if main:
        return main, 'main'
    return (dict(items[0]), 'candidate') if items else (None, 'none')


def build(studio, pid, sid):
    from backend.production_entities import state
    with studio.connect() as db:
        if not db.execute("SELECT 1 FROM production_nodes WHERE id=? AND production_id=? AND kind='series'", (sid, pid)).fetchone():
            raise HTTPException(404, 'Серия не найдена в выбранном проекте')
        scenes = [dict(r) for r in db.execute("SELECT * FROM production_nodes WHERE production_id=? AND parent_id=? AND kind='episode' ORDER BY number,id", (pid, sid))]
        rows = []
        for scene in scenes:
            for frame in db.execute("SELECT * FROM production_nodes WHERE production_id=? AND parent_id=? AND kind='frame' ORDER BY number,id", (pid, scene['id'])):
                frame = dict(frame)
                _, selection, _ = state(db, pid, frame['id'])
                files = {k: db.execute("SELECT * FROM production_files WHERE node_id=? AND kind=? ORDER BY created_at DESC,id DESC", (frame['id'], k)).fetchall() for k in ('image', 'video')}

                plan = visual_plan.clean(visual_plan.stored(db, 'visual_plans', frame['id']))
                (image, image_choice), (video, video_choice) = choose(files['image'], selection['selected_image_file_id']), choose(files['video'], selection['selected_video_file_id'])
                sound = [dict(c) for c in db.execute('''SELECT c.kind,c.text,c.level_db,c.start_s,c.duration_s,COALESCE(f.relative_path,'') AS file
                    FROM frame_sound_cues c LEFT JOIN production_files f ON f.id=c.file_id WHERE c.frame_id=? AND c.archived=0
                    ORDER BY c.start_s,c.created_at''', (frame['id'],))]
                rows.append({'scene': scene, 'frame': frame, 'image': image, 'video': video, 'image_choice': image_choice,
                             'video_choice': video_choice, 'plan': plan, 'sound': sound})
    analyses = []
    for row in rows:
        result = None
        if row['image']:
            try:
                from PIL import Image
                path = folders.checked_path(studio, row['image']['relative_path'])
                if path.is_file():
                    result = frame_analysis.analyze_image(Image.open(path))
            except Exception:
                result = None
        analyses.append(result)
    out = []
    for i, row in enumerate(rows):
        video = row['video']
        seconds = None
        if video:
            path = folders.checked_path(studio, video['relative_path'])
            seconds = duration(studio, path) if path.is_file() else None
        cut = None
        if i + 1 < len(rows) and analyses[i] and analyses[i + 1]:
            parts = frame_analysis.compare(analyses[i], analyses[i + 1])
            cut = {'score': score(parts), 'label': label(score(parts)), **parts}
        plan = row['plan']
        jump = None
        if i + 1 < len(rows):
            a, b = plan['sector_end'], rows[i + 1]['plan']['sector_start']
            jump = 'прыжок' if a and b and a != b else ('гладкая' if a and b else '')
        out.append({
            'order': i + 1, 'scene': row['scene']['number'], 'frame': row['frame']['number'], 'title': row['frame']['title'],
            'video': video['relative_path'] if video else '', 'image': row['image']['relative_path'] if row['image'] else '',
            'duration': seconds, 'sector_start': plan['sector_start'], 'sector_end': plan['sector_end'], 'sector_cut': jump,
            'image_cut': cut, 'space': plan['space'], 'line': plan['line'], 'story': plan['story'], 'visual': plan['visual'], 'note': plan['note'],
            'image_choice': row['image_choice'], 'video_choice': row['video_choice'], 'sound': row['sound'],
        })
    timed = [r['duration'] for r in out if r['duration']]
    warnings = []
    for r in out:
        if r['duration'] and r['duration'] > LONG_SHOT_SECONDS:
            warnings.append(f"Кадр {r['scene']}.{r['frame']} длится {r['duration']} с: монтажный ритм на таком кадре не ощущается; оставь, если это осознанный длинный план.")
        if not r['video']:
            warnings.append(f"У кадра {r['scene']}.{r['frame']} нет видео: в монтаже будет пропуск.")
        elif r['video_choice'] == 'candidate':
            warnings.append(f"У кадра {r['scene']}.{r['frame']} видео не утверждено: взят последний дубль (предварительно). Выбери главное видео на доске.")
    for i in range(len(out) - 2):
        trio = out[i:i + 3]
        if trio[0]['space'] and all(t['space'] == trio[0]['space'] and t['line'] == trio[0]['line'] for t in trio):
            warnings.append(f"Кадры {trio[0]['scene']}.{trio[0]['frame']}–{trio[2]['scene']}.{trio[2]['frame']} повторяют пространство и линию без роста напряжения.")
    approved = sum(1 for r in out if r['video_choice'] == 'main')
    summary = {'shots': len(out), 'with_video': sum(1 for r in out if r['video']), 'approved_videos': approved,
               'ready': bool(out) and approved == len(out), 'cuts': max(0, len(out) - 1),
               'total_seconds': round(sum(timed), 2) if timed else None,
               'average_seconds': round(sum(timed) / len(timed), 2) if timed else None,
               'cuts_per_minute': round((len(timed) - 1) / (sum(timed) / 60), 1) if len(timed) > 1 and sum(timed) else None}
    return {'summary': summary, 'warnings': warnings, 'rows': out}


CHOICE = {'main': 'главное', 'candidate': 'предварительно', 'none': ''}
SOUND_KIND = {'voice': 'Реплика', 'ambience': 'Атмосфера', 'sfx': 'SFX', 'music': 'Музыка'}
HEADER = ['№', 'Сцена', 'Кадр', 'Название', 'Видео', 'Выбор видео', 'Картинка', 'Длительность, с', 'Сектор начало', 'Сектор конец', 'Склейка по сектору',
          'Склейка по картинке', 'Пространство', 'Линия', 'Сюжет 0-10', 'Картинка 0-10', 'Заметка', 'Звук']


def sound_text(cues):
    """Звук кадра одной ячейкой: тип, уровень, смещение от начала кадра и файл."""
    return '; '.join(f"{SOUND_KIND.get(c['kind'], c['kind'])} {c['level_db']:g} дБ с {c['start_s']:g} с: "
                     + (Path(c['file']).name if c['file'] else 'нет файла') + (f" «{c['text']}»" if c['text'] else '') for c in cues)


def to_csv(data):
    stream = io.StringIO()
    writer = csv.writer(stream, delimiter=';')
    writer.writerow(HEADER)
    for r in data['rows']:
        writer.writerow([r['order'], r['scene'], r['frame'], r['title'], r['video'], CHOICE[r['video_choice']], r['image'], r['duration'] if r['duration'] is not None else '',
                         r['sector_start'] or '', r['sector_end'] or '', r['sector_cut'] or '', r['image_cut']['label'] if r['image_cut'] else '',
                         r['space'], r['line'], '' if r['story'] is None else r['story'], '' if r['visual'] is None else r['visual'], r['note'],
                         sound_text(r['sound'])])
    return '﻿' + stream.getvalue()


def vertical_prompt(db, pid, nid):
    node = db.execute('SELECT kind FROM production_nodes WHERE id=? AND production_id=?', (nid, pid)).fetchone()
    if not node:
        raise HTTPException(404, 'Карточка не найдена в этом проекте')
    if node['kind'] != 'frame':
        raise HTTPException(400, 'Вертикальная версия задаётся для кадра')
    plan = visual_plan.clean(visual_plan.stored(db, 'visual_plans', nid))
    parts = [VERTICAL_RULES]
    if plan['space'] in SPACE_VERTICAL:
        parts.append(SPACE_VERTICAL[plan['space']])
    rules = visual_plan.rules_text(db, pid, nid)
    return '\n'.join(parts) + ('\n\n' + rules if rules else '')


# Дорожки пакета CapCut; атмосфера идёт фоном вместе с шумами.
CAPCUT_TRACK = {'voice': 'voice', 'music': 'music', 'sfx': 'sfx', 'ambience': 'sfx'}


class CapcutExport(BaseModel):
    draft: bool = False


def export_capcut(studio, pid, sid, draft):
    """Пакет для ручного монтажа в 03_Монтаж серии: выбранные клипы, звук кадров и проверка пакета.
    Без draft выгружаются только кадры с главным видео; черновик явно помечен в имени папки."""
    from tools import capcut_handoff  # tools/ лежит в репозитории рядом с backend и не входит в облачный образ
    data = build(studio, pid, sid)
    if not data['rows']:
        raise HTTPException(409, 'В серии нет кадров: выгружать нечего')
    waiting = [f"{r['scene']}.{r['frame']}" for r in data['rows'] if r['video_choice'] != 'main']
    if waiting and not draft:
        raise HTTPException(409, f"Не выбрано главное видео у кадров {', '.join(waiting)}. Выбери главные дубли на доске или собери черновой пакет.")
    series = folders.node(studio, pid, sid)
    episodes = Path(series['relative_dir']) / '02_Эпизоды'
    media_root = folders.checked_path(studio, str(episodes))
    montage = folders.checked_path(studio, str(Path(series['relative_dir']) / '03_Монтаж'))
    name = f"CapCut_{datetime.now():%Y%m%d-%H%M%S}_{uuid.uuid4().hex[:4]}" + ('_ЧЕРНОВИК' if draft else '')

    def inside(relative):
        return str(Path(relative).relative_to(episodes)) if relative else ''
    rows = [{**r, 'video': inside(r['video']), 'image': inside(r['image']),
             'sound': [{**c, 'file': inside(c['file'])} for c in r['sound']]} for r in data['rows']]
    tracks = {}
    for row in rows:
        for cue in row['sound']:
            if cue['file']:
                tracks.setdefault(CAPCUT_TRACK.get(cue['kind'], 'sfx'), []).append(cue['file'])
    # Студийный лист со звуком по кадрам лежит рядом с пакетом: сам пакет звук по кадрам не описывает.
    montage.mkdir(parents=True, exist_ok=True)
    sheet = montage / (name + '_монтажный_лист.json')
    sheet.write_text(json.dumps({**data, 'rows': rows, 'draft': draft}, ensure_ascii=False, indent=2), encoding='utf-8')
    (montage / (name + '_монтажный_лист.csv')).write_text(to_csv(data), encoding='utf-8')
    try:
        manifest = capcut_handoff.export_handoff(sheet, media_root, montage / name, audio_tracks=tracks or None)
    except capcut_handoff.HandoffError as exc:
        raise HTTPException(400, f'Пакет не собран: {exc}') from exc
    check = capcut_handoff.verify_package(montage / name)
    return {'folder': str(montage / name), 'relative': str(Path(series['relative_dir']) / '03_Монтаж' / name),
            'draft': draft, 'waiting': waiting, 'status': manifest['status'], 'ready_for_montage': manifest['ready_for_montage'],
            'counts': manifest['counts'], 'issues': manifest['issues'], 'verify': check}


def register(app, studio):
    @app.get('/api/productions/{pid}/series/{sid}/edit-list')
    def edit_list(pid: str, sid: str, format: str = 'json'):
        data = build(studio, pid, sid)
        if format == 'csv':
            return Response(to_csv(data), media_type='text/csv; charset=utf-8',
                            headers={'Content-Disposition': 'attachment; filename="edit-list.csv"'})
        if format != 'json':
            raise HTTPException(400, 'Формат должен быть json или csv')
        return data

    @app.post('/api/productions/{pid}/series/{sid}/capcut')
    def capcut(pid: str, sid: str, body: CapcutExport):
        return export_capcut(studio, pid, sid, body.draft)

    @app.get('/api/productions/{pid}/nodes/{nid}/vertical-prompt')
    def vertical(pid: str, nid: str):
        with studio.connect() as db:
            return {'prompt': vertical_prompt(db, pid, nid)}

    @app.get('/api/projects/{project_id}/visual-rules-prompt')
    def project_rules(project_id: str):
        studio.project(project_id)
        membership = folders.link(studio, project_id)
        if not membership or not membership['node_id']:
            return {'prompt': ''}
        with studio.connect() as db:
            return {'prompt': visual_plan.rules_text(db, membership['production_id'], membership['node_id'])}

    @app.get('/api/projects/{project_id}/composition-brief')
    def project_composition(project_id: str):
        studio.project(project_id)
        membership = folders.link(studio, project_id)
        with studio.connect() as db:
            if not membership or not membership['node_id']:
                return {'prompt': visual_plan.composition_brief(db, '', '')}
            return {'prompt': visual_plan.composition_brief(db, membership['production_id'], membership['node_id'])}
