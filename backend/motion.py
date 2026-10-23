"""Motion graphics for the edit: series intro and character lower-thirds rendered locally by HyperFrames into the series 03_Монтаж folder."""
import json
import shutil
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from backend import production_folders as folders

MOTION_ROOT = Path(__file__).resolve().parent.parent / 'motion'
HYPERFRAMES = 'hyperframes@0.8.172'  # pinned so renders stay reproducible
# template id -> folder title, allowed variables, output format (mov keeps the alpha channel for CapCut overlays)
TEMPLATES = {
    'intro': {'title': 'Заставка', 'fields': ('series', 'episode', 'caption'), 'format': 'mp4'},
    'lower-third': {'title': 'Плашка', 'fields': ('name', 'role'), 'format': 'mov'},
}
SIZES = {'16:9': (1920, 1080), '9:16': (1080, 1920)}
RENDER_TIMEOUT = 600
render_lock = threading.Lock()  # one Chrome render at a time; a second click waits instead of doubling the load


class MotionRender(BaseModel):
    template: Literal['intro', 'lower-third']
    aspect: Literal['16:9', '9:16'] = '16:9'
    values: dict[str, str] = Field(default_factory=dict)


def prepare(template, aspect, workdir):
    """Copies the template and shared assets into workdir and sets the canvas size; returns the project dir."""
    width, height = SIZES[aspect]
    project = Path(workdir) / 'project'
    shutil.copytree(MOTION_ROOT / template, project)
    shutil.copytree(MOTION_ROOT / 'assets', project / 'assets')
    page = project / 'index.html'
    html = page.read_text(encoding='utf-8')
    html = html.replace('width=1920, height=1080', f'width={width}, height={height}')
    html = html.replace('data-width="1920" data-height="1080"', f'data-width="{width}" data-height="{height}"')
    page.write_text(html, encoding='utf-8')
    return project


def clean_values(template, values):
    fields = TEMPLATES[template]['fields']
    unknown = set(values) - set(fields)
    if unknown:
        raise HTTPException(400, 'Лишние поля: ' + ', '.join(sorted(unknown)))
    out = {}
    for key, value in values.items():
        value = value.strip()
        if len(value) > 80:
            raise HTTPException(400, 'Текст длиннее 80 символов')
        if value:
            out[key] = value
    return out


def render(studio, pid, sid, body):
    with studio.connect() as db:
        series = db.execute("SELECT * FROM production_nodes WHERE id=? AND production_id=? AND kind='series'", (sid, pid)).fetchone()
    if not series:
        raise HTTPException(404, 'Серия не найдена в выбранном проекте')
    npx = shutil.which('npx')
    if not npx:
        raise HTTPException(503, 'Для моушна нужен Node.js (npx) на этом компьютере')
    spec = TEMPLATES[body.template]
    values = clean_values(body.template, body.values)
    with tempfile.TemporaryDirectory(prefix='motion-') as workdir:
        project = prepare(body.template, body.aspect, workdir)
        variables = Path(workdir) / 'variables.json'
        variables.write_text(json.dumps(values, ensure_ascii=False), encoding='utf-8')
        output = Path(workdir) / ('out.' + spec['format'])
        # variables go through a file: JSON in argv is mangled by cmd.exe quoting of npx.cmd on Windows
        command = [npx, '--yes', HYPERFRAMES, 'render', str(project), '--variables-file', str(variables), '-q', 'high', '-o', str(output)]
        if spec['format'] != 'mp4':
            command += ['--format', spec['format']]
        with render_lock:
            try:
                result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=RENDER_TIMEOUT)
            except subprocess.TimeoutExpired:
                raise HTTPException(504, 'Рендер не уложился в 10 минут')
        if result.returncode != 0 or not output.is_file() or not output.stat().st_size:
            tail = (result.stderr or result.stdout or '').strip().splitlines()[-5:]
            raise HTTPException(502, 'Рендер не удался: ' + ' | '.join(tail))
        fid = uuid.uuid4().hex
        label = folders.safe_name(values.get('name') or values.get('episode') or values.get('series') or spec['title'])
        name = f"{spec['title']}_{label}_{body.aspect.replace(':', 'x')}.{spec['format']}"
        relative = str(Path(series['relative_dir']) / '03_Монтаж' / (fid[:8] + '_' + name))
        target = folders.checked_path(studio, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(output), target)
    with studio.connect() as db:
        db.execute('INSERT INTO production_files(id,production_id,node_id,asset_id,filename,relative_path,kind,created_at) VALUES(?,?,?,?,?,?,?,?)',
                   (fid, pid, sid, None, name, relative, 'video', studio.now()))
    return {'file_id': fid, 'filename': name, 'url': '/api/production-files/' + fid}


def register(app, studio):
    @app.post('/api/productions/{pid}/series/{sid}/motion')
    def motion_render(pid: str, sid: str, body: MotionRender):
        """Бесплатный локальный рендер заставки или плашки с именем в папку 03_Монтаж серии."""
        return render(studio, pid, sid, body)
