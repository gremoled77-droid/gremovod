"""Local, ordered media package for manual import into CapCut; never a native draft."""
import csv
import io
import tempfile
import zipfile

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from backend import production_folders as folders, production_entities, sound


def csv_text(header, rows):
    out = io.StringIO()
    writer = csv.writer(out, delimiter=';')
    writer.writerow(header)
    writer.writerows(rows)
    return '\ufeff' + out.getvalue()


def package(studio, pid, sid):
    """Build from registered files of this series only, never by walking user folders."""
    with studio.connect() as db:
        series = db.execute("SELECT * FROM production_nodes WHERE production_id=? AND id=? AND kind='series'", (pid, sid)).fetchone()
        if not series:
            raise HTTPException(404, 'Серия не найдена в выбранном проекте')
        series = dict(series)
        scenes = [dict(r) for r in db.execute("SELECT * FROM production_nodes WHERE production_id=? AND parent_id=? AND kind='episode' ORDER BY number,id", (pid, sid))]
        shots, node_ids = [], [sid]
        labels = {sid: 'Серия: ' + series['title']}
        for scene in scenes:
            node_ids.append(scene['id'])
            labels[scene['id']] = f"Сцена {scene['number']}: {scene['title']}"
            for frame in db.execute("SELECT * FROM production_nodes WHERE production_id=? AND parent_id=? AND kind='frame' ORDER BY number,id", (pid, scene['id'])):
                frame = dict(frame)
                node_ids.append(frame['id'])
                labels[frame['id']] = f"Кадр {scene['number']}.{frame['number']}: {frame['title']}"
                _, selection, _ = production_entities.state(db, pid, frame['id'])
                shots.append((scene, frame, selection))
        files = {}
        for nid in node_ids:
            files[nid] = [dict(r) for r in db.execute('SELECT * FROM production_files WHERE production_id=? AND node_id=? ORDER BY created_at DESC,id DESC', (pid, nid))]
        cues = sound.series_cues(db, pid, sid)
        heroes = {r['id']: r['title'] for r in db.execute("SELECT id,title FROM production_nodes WHERE production_id=? AND kind='character'", (pid,))}

    # Restrict even database paths to the requested series, in addition to the production root.
    scope = folders.checked_path(studio, series['relative_dir'])
    archive = tempfile.TemporaryFile()
    media, warnings, exported = [], [], {}
    try:
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as z:
            def add(row, name):
                path = folders.checked_path(studio, row['relative_path'])
                if not path.is_relative_to(scope):
                    raise HTTPException(400, 'Файл выходит за папку выбранной серии')
                if not path.is_file():
                    warnings.append('Файл отсутствует: ' + name)
                    return ''
                z.write(path, name)
                exported[row['id']] = name
                return name

            for order, (scene, frame, selection) in enumerate(shots, 1):
                names, sources = {}, []
                for kind, folder in (('video', '01_Видео'), ('image', '02_Кадры')):
                    items = [f for f in files[frame['id']] if f['kind'] == kind]
                    chosen = selection['selected_' + kind + '_file_id']
                    selected = next((f for f in items if f['id'] == chosen), None)
                    if chosen and selected is None:
                        warnings.append(f'Кадр {order}: выбранный {kind} недоступен; другой дубль не подставлен.')
                    if not chosen and items:
                        selected = items[0]
                        sources.append(kind + ': последний дубль (главный не выбран)')
                    elif selected:
                        sources.append(kind + ': главный дубль')
                    names[kind] = ''
                    if selected:
                        filename = folders.safe_name(selected['filename'])
                        names[kind] = add(selected, f'{folder}/{order:04d}_{filename}')
                if not names['video']:
                    warnings.append(f'Кадр {order}: нет видео; используйте картинку или завершите кадр.')
                media.append([order, scene['number'], frame['number'], frame['title'], names['video'], names['image'], '; '.join(sources)])

            audio_rows = []
            for index, nid in enumerate(node_ids, 1):
                for number, row in enumerate(reversed(files[nid]), 1):
                    if row['kind'] != 'audio':
                        continue
                    filename = folders.safe_name(row['filename'])
                    name = add(row, f'03_Звук/{index:04d}_{number:03d}_{filename}')
                    audio_rows.append([labels[nid], name, row['filename']])
            for frame in cues:
                for cue in frame['cues']:
                    name = exported.get(cue['file_id'], '')
                    cue['filename'] = name
                    cue['status'] = 'file' if name else 'plan'
            z.writestr('edit-list.csv', csv_text(['№', 'Сцена', 'Кадр', 'Название', 'Видео', 'Картинка', 'Выбор дубля'], media))
            z.writestr('audio-files.csv', csv_text(['Карточка', 'Файл в архиве', 'Исходное название'], audio_rows))
            z.writestr('sound-list.csv', sound.to_csv(cues, heroes))
            instructions = (
                'КОМПЛЕКТ ДЛЯ РУЧНОГО МОНТАЖА В CAPCUT\n\n'
                '1. Распакуйте ZIP в отдельную папку и создайте проект CapCut.\n'
                '2. Импортируйте 01_Видео и расположите клипы по номерам из edit-list.csv.\n'
                '3. В 02_Кадры лежат опорные изображения; они также могут заменить отсутствующее видео.\n'
                '4. Добавьте файлы из 03_Звук на звуковые дорожки. sound-list.csv задаёт смещение относительно начала кадра, длительность и уровень.\n'
                '5. audio-files.csv перечисляет весь прикреплённый звук кадров, сцен и серии, включая файлы без звуковых заметок.\n\n'
                'Это исходники и списки монтажа, а не нативный проект CapCut. Обрезка, длительности картинок, переходы и синхронизация выполняются вручную.\n'
                'Выбираются главные дубли. Если главный не назначен, берётся последний зарегистрированный дубль; это отмечено в edit-list.csv.\n'
                'Файлы не перекодированы. Звуковые заметки без готового файла остаются планом в sound-list.csv.\n\n'
                'ПРЕДУПРЕЖДЕНИЯ\n' + ('\n'.join(warnings) if warnings else 'Нет.') + '\n'
            )
            z.writestr('README.txt', instructions.encode('utf-8-sig'))
        archive.seek(0)
        return archive
    except BaseException:
        archive.close()
        raise


def register(app, studio):
    @app.get('/api/productions/{pid}/series/{sid}/export.zip')
    def export_series(pid: str, sid: str):
        archive = package(studio, pid, sid)

        def chunks():
            try:
                while chunk := archive.read(1024 * 1024):
                    yield chunk
            finally:
                archive.close()

        return StreamingResponse(chunks(), media_type='application/zip', headers={
            'Content-Disposition': 'attachment; filename="capcut-media.zip"',
            'Cache-Control': 'no-store',
        })
