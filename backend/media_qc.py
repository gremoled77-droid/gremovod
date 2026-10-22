"""N34 — техническое QC итогового файла: локальные измерения, 0 LLM.

Проверяем объективное: потоки, длительность, частоту кадров, разрешение, кодеки,
битрейт, декодируемость. Отдельно снимаем наблюдения — громкость LUFS, тишину,
чёрные кадры, зависание. Наблюдения — сигналы, а не вердикт: художественную оценку
здесь не даём, PASS_TECHNICAL означает «технически соответствует ожиданиям».

Роли. Воркер (CLI-режим этого модуля) снимает измерения и подписывает отчёт.
Студия — доверенный backend: проверяет подпись, сверяет хеш мастера со своим
собственным файлом и сама выводит вердикт из измерений. Готовый вердикт из
отчёта не принимается: считает его студия.
"""
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, Field

from backend import security

BLOCKED = 'BLOCKED'
FAIL = 'FAIL'
PASS_TECHNICAL = 'PASS_TECHNICAL'
CHUNK = 1024 * 1024


def sha256_file(path: Path) -> str:
    """Хеш файла мастера: отчёт принимается только для того же байт-в-байт файла."""
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        while True:
            chunk = source.read(CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _optional(runner, args):
    """Запуск необязательного измерения: нет инструмента или нет сигнала — не ошибка."""
    try:
        return runner(args)
    except (HTTPException, OSError, subprocess.SubprocessError):
        return None


def _pairs(starts, ends):
    result = []
    for start, end in zip(starts, ends):
        try:
            low, high = float(start), float(end)
        except (TypeError, ValueError):
            continue
        if high < low:
            continue
        result.append({'start_ms': int(round(low * 1000)), 'end_ms': int(round(high * 1000))})
    return result


def _spans(starts, durations):
    result = []
    for start, duration in zip(starts, durations):
        try:
            low, length = float(start), float(duration)
        except (TypeError, ValueError):
            continue
        result.append({'start_ms': int(round(low * 1000)), 'end_ms': int(round((low + length) * 1000))})
    return result


def _fps(stream):
    raw = str((stream or {}).get('avg_frame_rate') or '')
    if '/' in raw:
        numerator, _, denominator = raw.partition('/')
        try:
            top, bottom = float(numerator), float(denominator)
        except ValueError:
            return 0.0
        return round(top / bottom, 3) if bottom else 0.0
    try:
        return round(float(raw), 3)
    except ValueError:
        return 0.0


def _probe(runner, path: Path):
    """Метаданные мастера. Нет ffprobe или файл не читается — None."""
    if not shutil.which('ffprobe'):
        return None
    try:
        raw = runner(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', str(path)])
        probe = json.loads(raw.stdout)
    except (HTTPException, TypeError, ValueError, OSError, subprocess.SubprocessError):
        return None
    if not isinstance(probe, dict):
        return None
    streams = probe.get('streams') if isinstance(probe.get('streams'), list) else []
    fmt = probe.get('format') if isinstance(probe.get('format'), dict) else {}
    video = next((stream for stream in streams if stream.get('codec_type') == 'video'), None)
    audio = next((stream for stream in streams if stream.get('codec_type') == 'audio'), None)
    try:
        duration_ms = int(round(float(fmt.get('duration') or 0) * 1000))
    except (TypeError, ValueError):
        duration_ms = 0
    try:
        bitrate = int(fmt.get('bit_rate') or 0)
    except (TypeError, ValueError):
        bitrate = 0
    return {
        'duration_ms': duration_ms,
        'format': str(fmt.get('format_name') or ''),
        'bitrate': bitrate,
        'width': int(video.get('width') or 0) if video else 0,
        'height': int(video.get('height') or 0) if video else 0,
        'fps': _fps(video),
        'video_codec': str(video.get('codec_name') or '') if video else '',
        'audio_codec': str(audio.get('codec_name') or '') if audio else '',
        'audio_streams': sum(1 for stream in streams if stream.get('codec_type') == 'audio'),
        'sample_rate': int(audio.get('sample_rate') or 0) if audio else 0,
        'decodes': _decodes(runner, path),
    }


def _decodes(runner, path: Path) -> bool:
    if not shutil.which('ffmpeg'):
        return False
    try:
        runner(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'null', '-'])
        return True
    except (HTTPException, OSError, subprocess.SubprocessError):
        return False


def _observe(runner, path: Path):
    """Сигналы: громкость, тишина, чёрные кадры, зависание. Не влияют на вердикт."""
    observations = {'lufs_integrated': None, 'silence_intervals': [], 'black_intervals': [],
                    'freeze_intervals': [], 'unavailable': []}
    if not shutil.which('ffmpeg'):
        observations['unavailable'] = ['lufs_integrated', 'silence_intervals', 'black_intervals', 'freeze_intervals']
        return observations
    scan = _optional(runner, ['ffmpeg', '-hide_banner', '-nostats', '-i', str(path),
                              '-filter_complex', 'ebur128=peak=true', '-f', 'null', '-'])
    values = re.findall(r'I:\s*(-?\d+(?:\.\d+)?)\s*LUFS', scan.stderr) if scan else []
    if values:
        observations['lufs_integrated'] = float(values[-1])
    else:
        observations['unavailable'].append('lufs_integrated')
    scan = _optional(runner, ['ffmpeg', '-hide_banner', '-nostats', '-i', str(path),
                              '-af', 'silencedetect=noise=-50dB:d=0.5', '-f', 'null', '-'])
    if scan:
        observations['silence_intervals'] = _pairs(
            re.findall(r'silence_start:\s*([\d.]+)', scan.stderr),
            re.findall(r'silence_end:\s*([\d.]+)', scan.stderr))
    else:
        observations['unavailable'].append('silence_intervals')
    scan = _optional(runner, ['ffmpeg', '-hide_banner', '-nostats', '-i', str(path),
                              '-vf', 'blackdetect=d=0.2:pix_th=0.10', '-an', '-f', 'null', '-'])
    if scan:
        observations['black_intervals'] = _pairs(
            re.findall(r'black_start:\s*([\d.]+)', scan.stderr),
            re.findall(r'black_end:\s*([\d.]+)', scan.stderr))
    else:
        observations['unavailable'].append('black_intervals')
    scan = _optional(runner, ['ffmpeg', '-hide_banner', '-nostats', '-i', str(path),
                              '-vf', 'freezedetect=n=-60dB:d=1', '-an', '-f', 'null', '-'])
    if scan:
        observations['freeze_intervals'] = _spans(
            re.findall(r'freeze_start:\s*([\d.]+)', scan.stderr),
            re.findall(r'freeze_duration:\s*([\d.]+)', scan.stderr))
    else:
        observations['unavailable'].append('freeze_intervals')
    return observations


def measure(runner, path: Path) -> dict:
    """Измерения мастера: метаданные и сигналы. Отдельные сигналы могут отсутствовать."""
    return {'master': _probe(runner, path), 'observations': _observe(runner, path)}


def _requirements(master, manifest):
    """Проверки по ожидаемому манифесту. Возвращает список (имя, ожидание, факт, выполнено)."""
    checks = []
    for field, label in (('width', 'ширина'), ('height', 'высота')):
        if manifest.get(field) is not None:
            expected = int(manifest[field])
            actual = int(master.get(field) or 0)
            checks.append((label, expected, actual, actual == expected))
    if manifest.get('fps') is not None:
        expected = float(manifest['fps'])
        actual = float(master.get('fps') or 0)
        tolerance = float(manifest.get('fps_tolerance') or 0.5)
        checks.append(('частота кадров', expected, actual, abs(actual - expected) <= tolerance))
    if manifest.get('duration_ms') is not None:
        expected = int(manifest['duration_ms'])
        actual = int(master.get('duration_ms') or 0)
        tolerance = int(manifest.get('duration_tolerance_ms') or 1000)
        checks.append(('длительность, мс', expected, actual, abs(actual - expected) <= tolerance))
    if manifest.get('container'):
        expected = str(manifest['container']).strip().lower()
        names = {part.strip().lower() for part in str(master.get('format') or '').split(',')}
        checks.append(('контейнер', expected, master.get('format'), expected in names))
    for field, label in (('video_codec', 'видеокодек'), ('audio_codec', 'аудиокодек')):
        if manifest.get(field):
            expected = str(manifest[field]).strip().lower()
            actual = str(master.get(field) or '').strip().lower()
            checks.append((label, expected, actual, actual == expected))
    return checks


def verdict(measurement: dict, manifest: dict) -> dict:
    """Вердикт по измерениям. Чистая функция: тот же вход — тот же вердикт.

    BLOCKED — измерить нельзя (нет файла, нет ffprobe, нет обязательной дорожки).
    FAIL — измерили, но ожиданиям не соответствует.
    PASS_TECHNICAL — соответствует. Наблюдения в вердикт не входят.
    """
    measurement = measurement or {}
    manifest = manifest or {}
    master = measurement.get('master') or {}
    observations = measurement.get('observations') or {}
    if not master:
        return {'status': BLOCKED, 'reason': 'ffprobe недоступен или файл не читается',
                'checks': [], 'observations': observations}
    reason = ''
    if not master.get('width') or not master.get('height'):
        reason = 'в файле нет корректного видеопотока'
    elif manifest.get('require_audio') and not master.get('audio_codec'):
        reason = 'в файле нет аудиодорожки, а манифест её требует'
    elif master.get('decodes') is False:
        reason = 'файл не декодируется'
    if reason:
        return {'status': BLOCKED, 'reason': reason, 'checks': [], 'observations': observations}
    checks = [{'name': name, 'expected': expected, 'actual': actual, 'ok': ok}
              for name, expected, actual, ok in _requirements(master, manifest)]
    status = PASS_TECHNICAL if all(check['ok'] for check in checks) else FAIL
    return {'status': status, 'reason': '', 'checks': checks, 'observations': observations}


def build_report(project_id, artifact_id, path: Path, measurement: dict, manifest: dict) -> dict:
    """Отчёт воркера: что измерено, для какого файла и по какому манифесту."""
    try:
        digest = sha256_file(path)
    except OSError:
        digest = ''
    return {
        'project_id': project_id,
        'artifact_id': artifact_id,
        'master_sha256': digest,
        'master': measurement.get('master') or {},
        'observations': measurement.get('observations') or {},
        'manifest': manifest or {},
    }


class QcReportRequest(BaseModel):
    """Отчёт воркера с подписью и ожидаемый манифест от доверенного вызывающего."""
    report: dict = Field(default_factory=dict)
    signature: str = ''
    manifest: dict = Field(default_factory=dict)
    producer_profile_revision: str | None = None


class QcMeasureRequest(BaseModel):
    """Локальное измерение: студия меряет файл сама."""
    manifest: dict = Field(default_factory=dict)
    producer_profile_revision: str | None = None


def _artifact(studio, project_id, artifact_id):
    with studio.connect() as db:
        row = db.execute('SELECT * FROM release_artifacts WHERE id=? AND project_id=?',
                         (artifact_id, project_id)).fetchone()
    if row is None:
        raise HTTPException(404, 'Итоговый артефакт не найден')
    return row


def _artifact_path(studio, row) -> Path:
    with studio.connect() as db:
        asset = db.execute('SELECT filename FROM library_assets WHERE id=?', (row['library_asset_id'],)).fetchone()
    if asset is None:
        raise HTTPException(404, 'Файл выпуска не найден в библиотеке')
    root = Path(studio.LIBRARY_ROOT).resolve()
    path = (root / asset['filename']).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(400, 'Файл выпуска вне библиотеки')
    return path


def _store(studio, project_id, artifact_id, digest, result, signature, master=None):
    record = {
        'artifact_id': artifact_id,
        'project_id': project_id,
        'master_sha256': digest,
        'verdict': result['status'],
        'reason': result.get('reason') or '',
        'checks': json.dumps(result.get('checks') or [], ensure_ascii=False),
        'measurements': json.dumps(master or {}, ensure_ascii=False),
        'observations': json.dumps(result.get('observations') or {}, ensure_ascii=False),
        'signature': signature,
        'created_at': studio.now(),
    }
    with studio.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('''INSERT INTO release_artifact_qc
            (artifact_id,project_id,master_sha256,verdict,reason,checks,measurements,observations,signature,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(artifact_id) DO UPDATE SET
                project_id=excluded.project_id, master_sha256=excluded.master_sha256, verdict=excluded.verdict,
                reason=excluded.reason, checks=excluded.checks, measurements=excluded.measurements,
                observations=excluded.observations, signature=excluded.signature, created_at=excluded.created_at''',
            (record['artifact_id'], record['project_id'], record['master_sha256'], record['verdict'],
             record['reason'], record['checks'], record['measurements'], record['observations'],
             record['signature'], record['created_at']))
    return record


def _qc_record(studio, project_id, artifact_id):
    with studio.connect() as db:
        row = db.execute('SELECT * FROM release_artifact_qc WHERE artifact_id=? AND project_id=?',
                         (artifact_id, project_id)).fetchone()
    if row is None:
        raise HTTPException(404, 'Техническая проверка выпуска не проводилась')
    record = dict(row)
    for field in ('checks', 'measurements', 'observations'):
        try:
            record[field] = json.loads(record[field])
        except (TypeError, ValueError):
            record[field] = None
    return record


def _accept(studio, project_id, artifact_id, report, signature, manifest):
    """Проверка отчёта воркера и вывод вердикта.

    Подпись обязательна: подделанный или изменённый отчёт отклоняется. Файл
    недоступен и хеш не сошёлся — это BLOCKED, а не ошибка: по спецификации
    N34 такие условия означают «измерить нельзя», а не «ошибка запроса».
    """
    if not report:
        raise HTTPException(400, 'Пустой отчёт воркера')
    if not security.qc_verify(report, signature):
        raise HTTPException(400, 'Подпись отчёта неверна: отчёт изменён или подделан')
    if report.get('artifact_id') != artifact_id or report.get('project_id') != project_id:
        raise HTTPException(400, 'Отчёт относится к другому артефакту')
    path = _artifact_path(studio, _artifact(studio, project_id, artifact_id))
    observations = report.get('observations') or {}
    master = report.get('master') or {}
    if not path.is_file():
        result = {'status': BLOCKED, 'reason': 'файл мастера недоступен на диске',
                  'checks': [], 'observations': observations}
        _store(studio, project_id, artifact_id, str(report.get('master_sha256') or ''), result, signature, master)
        return result
    digest = sha256_file(path)
    if report.get('master_sha256') != digest:
        result = {'status': BLOCKED, 'reason': 'хеш мастера в отчёте не совпадает с файлом в библиотеке',
                  'checks': [], 'observations': observations}
        _store(studio, project_id, artifact_id, digest, result, signature, master)
        return result
    measurement = {'master': master, 'observations': observations}
    result = verdict(measurement, manifest)
    _store(studio, project_id, artifact_id, digest, result, signature, master)
    return result


def master_facts(studio, project_id, artifact_id):
    """Факты о мастере: путь, хеш, вердикт N34, измерения.

    Единый источник истины для технической проверки и для заморозки медиа в
    QA-контуре: и там, и там мастер — это один и тот же файл в библиотеке.
    """
    facts = {'exists': False, 'path': None, 'sha256': '', 'qc_verdict': '', 'qc_stale': False, 'measurements': {},
             'observations': {}, 'reason': 'итоговый артефакт не найден'}
    with studio.connect() as db:
        row = db.execute('SELECT * FROM release_artifacts WHERE id=? AND project_id=?',
                         (artifact_id, project_id)).fetchone()
        if row is None:
            return facts
        asset = db.execute('SELECT filename FROM library_assets WHERE id=?', (row['library_asset_id'],)).fetchone()
        try:
            qc = db.execute('SELECT * FROM release_artifact_qc WHERE artifact_id=?', (artifact_id,)).fetchone()
        except Exception:
            qc = None
    if asset is None:
        facts['reason'] = 'файл выпуска не найден в библиотеке'
        return facts
    root = Path(studio.LIBRARY_ROOT).resolve()
    path = (root / asset['filename']).resolve()
    if not path.is_relative_to(root):
        facts['reason'] = 'файл выпуска вне библиотеки'
        return facts
    facts['path'] = path
    facts['exists'] = path.is_file()
    if facts['exists']:
        facts['sha256'] = sha256_file(path)
        facts['reason'] = ''
    else:
        facts['reason'] = 'файл мастера отсутствует на диске'
    if qc is not None:
        facts['qc_verdict'] = qc['verdict'] or ''
        if facts['exists'] and (qc['master_sha256'] or '') != facts['sha256']:
            # QC относится к другим байтам: файл изменён после проверки, старый вердикт не наследуется
            facts['qc_verdict'], facts['qc_stale'] = BLOCKED, True
        for field, key in (('measurements', 'measurements'), ('observations', 'observations')):
            try:
                facts[key] = json.loads(qc[field])
            except (TypeError, ValueError):
                facts[key] = {}
    return facts


def register(app, studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS release_artifact_qc (
                artifact_id TEXT PRIMARY KEY REFERENCES release_artifacts(id) ON DELETE CASCADE,
                project_id TEXT NOT NULL,
                master_sha256 TEXT NOT NULL,
                verdict TEXT NOT NULL,
                reason TEXT NOT NULL,
                checks TEXT NOT NULL,
                measurements TEXT NOT NULL,
                observations TEXT NOT NULL,
                signature TEXT NOT NULL,
                created_at TEXT NOT NULL
            )''')

    @app.post('/api/projects/{project_id}/release-artifacts/{artifact_id}/qc')
    def accept_qc(project_id: str, artifact_id: str, body: QcReportRequest):
        """Приём подписанного отчёта воркера: подпись, хеш мастера, затем вердикт."""
        studio.project(project_id)
        _artifact(studio, project_id, artifact_id)
        result = _accept(studio, project_id, artifact_id, body.report, body.signature, body.manifest)
        return {'artifact_id': artifact_id, 'verdict': result['status'], 'reason': result.get('reason') or '',
                'checks': result.get('checks') or [], 'observations': result.get('observations') or {}}

    @app.post('/api/projects/{project_id}/release-artifacts/{artifact_id}/qc/measure')
    def measure_qc(project_id: str, artifact_id: str, body: QcMeasureRequest):
        """Локальное измерение: студия меряет файл сама и подписывает отчёт."""
        studio.project(project_id)
        path = _artifact_path(studio, _artifact(studio, project_id, artifact_id))
        measurement = measure(studio.cmd, path) if path.is_file() else {'master': None, 'observations': {}}
        report = build_report(project_id, artifact_id, path, measurement, body.manifest)
        signature = security.qc_sign(report)
        result = _accept(studio, project_id, artifact_id, report, signature, body.manifest)
        return {'artifact_id': artifact_id, 'verdict': result['status'], 'reason': result.get('reason') or '',
                'checks': result.get('checks') or [], 'observations': result.get('observations') or {},
                'master_sha256': report['master_sha256']}

    @app.get('/api/projects/{project_id}/release-artifacts/{artifact_id}/qc')
    def read_qc(project_id: str, artifact_id: str):
        """Сохранённый вердикт технической проверки."""
        studio.project(project_id)
        _artifact(studio, project_id, artifact_id)
        return _qc_record(studio, project_id, artifact_id)


def _cli_runner(args):
    """Запуск команды воркером: тот же контракт, что у studio.cmd."""
    if not shutil.which(args[0]):
        raise HTTPException(503, f'Не установлен {args[0]} — установи FFmpeg')
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=600, check=True)
    except subprocess.CalledProcessError as exc:
        raise HTTPException(422, {'error': 'FFmpeg: не удалось обработать медиа', 'detail': exc.stderr[-600:]})
    except subprocess.TimeoutExpired:
        raise HTTPException(504, 'Слишком долгий медиафайл')


def main_cli(argv=None):
    """Воркер N34: подписанный отчёт по файлу.

    Пример: python -m backend.media_qc master.mp4 --artifact-id id --project-id pid --manifest m.json --out report.json
    """
    import argparse

    parser = argparse.ArgumentParser(description='Воркер N34: измерения и подписанный отчёт')
    parser.add_argument('file')
    parser.add_argument('--project-id', default='')
    parser.add_argument('--artifact-id', default='')
    parser.add_argument('--manifest', default='{}')
    parser.add_argument('--out', default='')
    args = parser.parse_args(argv)
    path = Path(args.file)
    if not path.is_file():
        raise SystemExit('Файл не найден: ' + str(path))
    try:
        manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8')) if args.manifest != '{}' else {}
    except (OSError, ValueError):
        raise SystemExit('Манифест не прочитан: ' + args.manifest)
    measurement = measure(_cli_runner, path)
    report = build_report(args.project_id, args.artifact_id, path, measurement, manifest)
    report['signature'] = security.qc_sign(report)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main_cli())
