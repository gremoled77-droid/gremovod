"""Durable handoff to the user-owned Codex chat; never calls paid APIs.

The desktop chat must actively consume the queue. There is no supported server-side
wake API. Claimed work is never automatically retried after a worker disappears.
"""
import json
import secrets
import time
import uuid
from pathlib import Path

from fastapi import Header, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from backend.refinement import edit_context, PRESERVE_VISUAL
from backend import character_description, production_skills

THREAD_ID = '01a13e25-939c-7b73-9c0a-669abc8aa6a7'
CHAT_URL = f'codex://threads/{THREAD_ID}'
RUNTIME = Path(__file__).resolve().parents[1] / 'runtime' / 'prompt-chat'


class NativeRequest(BaseModel):
    project_id: str
    target: str = 'gpt-image-2.5'
    operation: str = 'generate'
    request_id: str = Field(min_length=16, max_length=100,pattern=r'^[A-Za-z0-9_-]+$')
    use_scene: bool = False
    brief: str = Field(default='', max_length=4000)  # готовый промпт из «Кадров» (только generate)
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=8)
    character_id: str | None = None
    production_id: str | None = None
    production_node_id: str | None = None
    entity_revision: str | None = None
    entity_instruction: str = Field(default='',max_length=4000)
    source_asset_id: str | None = None
    reference_asset_id: str | None = None
    edit_instruction: str = Field(default='',max_length=4000)


class Progress(BaseModel):
    identity: character_description.Identity | None = None
    status: str
    prompt: str = Field(default='', max_length=20000)
    message: str = Field(default='', max_length=2000)


def chat_rules(studio, body, context):
    """Правила задания для чата: базовые правила модели плюс производственные скиллы.

    Замок канона подключается для описания персонажа и для продакшн-карточки с сущностью,
    правило технического промпта — для видео-генератора. Тексты берутся из реестра,
    хэш файла сверяется с реестром: расхождение версий останавливает задание.
    """
    base = character_description.RULES if body.operation == 'describe_character' else studio.system_rules(studio.MODEL_SPECS[body.target])
    names = production_skills.for_native_chat(body.operation, studio.MODEL_SPECS[body.target].get('kind'), bool(context.get('entity')))
    packed = production_skills.context(names, getattr(body, 'entity_revision', None))
    overlap = [item for item in packed['conflicts'] if item['kind'] == 'scope_overlap']
    if overlap:
        raise HTTPException(409, 'Производственные скиллы конфликтуют: ' + '; '.join(item['detail'] for item in overlap))
    return production_skills.system_prompt(base, names)


def register(app, studio):
    def authenticate(value):
        path = RUNTIME / 'worker-token.txt'
        if not path.is_file() or not secrets.compare_digest(value or '', path.read_text().strip()):
            raise HTTPException(403, 'Нужен локальный ключ обработчика чата')

    def row(job_id):
        with studio.connect() as db:
            item = db.execute('SELECT * FROM native_chat_jobs WHERE id=?', (job_id,)).fetchone()
        if not item:
            raise HTTPException(404, 'Задание чата не найдено')
        return dict(item)

    def public(item):
        body=json.loads(item['request'])['body']
        return {k: item[k] for k in ('id', 'project_id', 'target', 'operation', 'status', 'prompt', 'message', 'asset_id', 'created_at', 'updated_at')} | {
            'chat_url': CHAT_URL, 'use_scene': json.loads(item['request'])['body'].get('use_scene',False),
            'source_asset_id':body.get('source_asset_id'),'reference_asset_id':body.get('reference_asset_id'),
            'edit_instruction':body.get('edit_instruction',''),
            'character_id':body.get('character_id'),
            'production_node_id':body.get('production_node_id'),
            'description_result':json.loads(item['prompt']) if item['operation']=='describe_character' and item['status']=='completed' else None,
            'camera_movement':json.loads(item['request']).get('context',{}).get('camera_movement'),
            'frame_composition':json.loads(item['request']).get('context',{}).get('frame_composition'),
            'image_url': '/api/library/' + item['asset_id'] + '/file' if item['asset_id'] else None}

    @app.on_event('startup')
    def setup():
        RUNTIME.mkdir(parents=True, exist_ok=True)
        token = RUNTIME / 'worker-token.txt'
        if not token.exists():
            token.write_text(secrets.token_urlsafe(32), encoding='utf-8')
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS native_chat_jobs (
                id TEXT PRIMARY KEY,project_id TEXT NOT NULL,target TEXT NOT NULL,
                operation TEXT NOT NULL,status TEXT NOT NULL,request TEXT NOT NULL,
                prompt TEXT NOT NULL,message TEXT NOT NULL,asset_id TEXT NOT NULL,
                created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
            db.execute('CREATE TABLE IF NOT EXISTS native_chat_worker(id INTEGER PRIMARY KEY,seen REAL NOT NULL,busy INTEGER NOT NULL)')

    @app.get('/api/chatgpt/status')
    def status():
        with studio.connect() as db:
            worker = db.execute('SELECT * FROM native_chat_worker WHERE id=1').fetchone()
        age = time.time() - worker['seen'] if worker else None
        online = age is not None and age < (600 if worker['busy'] else 90)
        return {'thread_id': THREAD_ID, 'chat_url': CHAT_URL, 'worker_online': online,
                'worker_busy': bool(worker and worker['busy'] and online),
                'automatic_wake': False, 'requested_image_model': 'gpt-image-2.5',
                'actual_image_model_selectable': False,
                'note': 'Обработка автоматическая, пока чат слушает очередь. Для запуска обработчика открой чат и напиши «Продолжай очередь студии».'}

    @app.get('/api/chatgpt/jobs')
    def listing(project_id: str):
        studio.project(project_id)
        with studio.connect() as db:
            items = db.execute('SELECT * FROM native_chat_jobs WHERE project_id=? ORDER BY created_at DESC LIMIT 100', (project_id,)).fetchall()
        return [public(dict(item)) for item in items]

    @app.post('/api/chatgpt/jobs')
    def enqueue(body: NativeRequest):
        if body.target not in studio.MODEL_SPECS:raise HTTPException(400,'Неизвестная целевая модель')
        if body.operation not in {'prompt', 'generate','edit','describe_character'}:
            raise HTTPException(400, 'Неизвестная операция')
        if body.operation in {'generate','edit'} and body.target not in {'gpt-image-2', 'gpt-image-2.5'}:
            raise HTTPException(400, 'В этом блоке изображения создаются через ChatGPT / GPT Image')
        if body.production_id or body.production_node_id:
            if not all([body.production_id,body.production_node_id,body.entity_revision]) or body.operation not in {'prompt','generate'} or body.use_scene or body.source_asset_id or body.reference_asset_id or body.edit_instruction:
                raise HTTPException(400,'Для карточки нужны проект, адресат и версия; допустимы prompt или generate')
            from backend import production_entities
            context=production_entities.context(studio,body)
        elif body.operation=='describe_character':
            if body.use_scene or body.source_asset_id or body.reference_asset_id or body.edit_instruction:raise HTTPException(400,'Распознавание использует только референсы персонажа')
            context=character_description.context(studio,body)
        elif body.operation=='edit':context=edit_context(studio,body)
        else:
            if body.source_asset_id or body.reference_asset_id or body.edit_instruction:
                raise HTTPException(400,'Исходники правки разрешены только для операции edit')
            if body.brief.strip():
                if body.operation not in {'generate','prompt'} or body.use_scene:
                    raise HTTPException(400,'Готовый промпт принимают только generate и prompt без сцены')
                override={'brief':body.brief.strip(),'assets':[{'asset_id':a,'role':'reference','note':''} for a in dict.fromkeys(body.reference_asset_ids)]}
                context = studio.compose_context(studio.ComposeRequest(project_id=body.project_id, target=body.target,use_scene=True,scene_override=override,provider='codex_chat'))
            else:
                context = studio.compose_context(studio.ComposeRequest(project_id=body.project_id, target=body.target,use_scene=body.use_scene,provider='codex_chat'))
        if body.target not in studio.MODEL_SPECS:raise HTTPException(400,'Неизвестная целевая модель')
        # Производственные скиллы: замок канона для описания персонажа и для продакшн-карточки,
        # правило технического промпта для видео-генератора. Тексты берутся из реестра,
        # хэш файла сверяется с реестром: расхождение останавливает задание.
        request = json.dumps({'body': body.model_dump(), 'context': context,
                              'rules': chat_rules(studio, body, context),
                              'quality_request': 'Highest available native quality. For edits keep source dimensions and aspect ratio where supported. Do not upscale or claim an unexposed model/size setting.',
                              'execution':{'intent':body.operation,'prompt_only':body.operation=='prompt','instructions':character_description.RULES if body.operation=='describe_character' else ('PROMPT ONLY. Read the supplied context and structured prompt_base choices. Prepare one coherent finished prompt for the selected model. Preserve reference roles and all explicit framing, lighting and seating constraints. Return it with prompt-ready. Do not call imagegen, generate media, upload images or invoke a paid API. Stop after the prompt is saved.' if body.operation=='prompt' else 'For edit: view each supplied local_path, then call built-in imagegen as an EDIT with referenced_image_paths in the given order. Image 1 is the target; Image 2 is only a detail reference. Follow preservation_contract. Do not recreate from text alone.')}}, ensure_ascii=False, sort_keys=True)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM native_chat_jobs WHERE id=?', (body.request_id,)).fetchone()
            if existing:
                if existing['request'] != request:
                    raise HTTPException(409, 'Этот ID уже принадлежит другому запросу')
                return public(dict(existing))
            if body.operation=='describe_character':
                db.execute("UPDATE native_chat_jobs SET status='cancelled',message='Заменено новым набором референсов',updated_at=? WHERE project_id=? AND operation='describe_character' AND status='queued' AND json_extract(request,'$.body.character_id')=?",(studio.now(),body.project_id,body.character_id))
            if db.execute("SELECT 1 FROM native_chat_jobs WHERE project_id=? AND status IN ('queued','preparing','generating')", (body.project_id,)).fetchone():
                raise HTTPException(409, 'В проекте уже есть незавершённое задание чата')
            stamp = studio.now()
            db.execute('INSERT INTO native_chat_jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (body.request_id, body.project_id, body.target, body.operation, 'queued', request, '', 'Ожидает распознавание референсов в GPT-чате' if body.operation=='describe_character' else 'Ожидает обработчик чата', '', stamp, stamp))
        return public(row(body.request_id))

    @app.post('/api/chatgpt/jobs/{job_id}/cancel')
    def cancel(job_id: str):
        with studio.connect() as db:
            updated = db.execute("UPDATE native_chat_jobs SET status='cancelled',message='Отменено до начала обработки',updated_at=? WHERE id=? AND status='queued'", (studio.now(), job_id)).rowcount
        if not updated:
            raise HTTPException(409, 'Обработку уже начали; повторный запуск может создать ещё одно изображение')
        return public(row(job_id))

    @app.post('/api/chatgpt/worker/claim')
    def claim(x_studio_worker: str | None = Header(default=None)):
        authenticate(x_studio_worker)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            busy = db.execute("SELECT 1 FROM native_chat_jobs WHERE status IN ('preparing','generating')").fetchone()
            item = None if busy else db.execute("SELECT * FROM native_chat_jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if item:
                db.execute("UPDATE native_chat_jobs SET status='preparing',message=?,updated_at=? WHERE id=?", ('GPT распознаёт референсы' if item['operation']=='describe_character' else 'GPT готовит промпт',studio.now(), item['id']))
            db.execute('INSERT INTO native_chat_worker VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET seen=excluded.seen,busy=excluded.busy', (time.time(), int(bool(item or busy))))
        if not item:
            return {'job': None}
        data = dict(item)
        return {'job': public(row(data['id'])), 'request': json.loads(data['request'])}

    @app.post('/api/chatgpt/worker/jobs/{job_id}/progress')
    def progress(job_id: str, body: Progress, x_studio_worker: str | None = Header(default=None)):
        authenticate(x_studio_worker)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            item = db.execute('SELECT * FROM native_chat_jobs WHERE id=?', (job_id,)).fetchone()
            if not item:
                raise HTTPException(404, 'Задание не найдено')
            if item['status'] not in {'preparing', 'generating'}:
                raise HTTPException(409, 'Задание больше не выполняется')
            final_prompt = body.prompt.strip() or item['prompt']
            if body.status == 'failed':
                state = 'failed'
            elif item['operation']=='describe_character' and item['status']=='preparing' and body.status=='identity_ready' and body.identity is not None:
                result=character_description.apply(db,studio,item,body.identity)
                final_prompt=json.dumps(result,ensure_ascii=False);state='completed'
            elif item['operation']!='describe_character' and item['status'] == 'preparing' and body.status == 'prompt_ready' and final_prompt:
                state = 'generating' if item['operation'] in {'generate','edit'} else 'completed'
                if item['operation']=='edit':final_prompt=PRESERVE_VISUAL+'\n\nREQUESTED CHANGE:\n'+final_prompt
                studio.validate_prompt(item['target'], final_prompt, len(json.loads(item['request'])['context']['references']))
                context = json.loads(item['request'])['context']
                db.execute('INSERT INTO prompt_versions VALUES(?,?,?,?,?,?,?,?,?,?)',
                           (uuid.uuid4().hex, item['project_id'], item['target'], final_prompt, json.dumps(context, ensure_ascii=False), 'codex_chat', 'gpt-6.1-sol', '{}', studio.RULES_VERSION, studio.now()))
                if not context.get('entity'):
                    project = db.execute('SELECT state FROM projects WHERE id=?', (item['project_id'],)).fetchone()
                    latest = json.loads(project['state'])
                    if item['operation']!='edit':latest.setdefault('prompts', {})[item['target']] = final_prompt
                    if json.loads(item['request'])['body'].get('use_scene'):
                        latest.setdefault('scene', {}).setdefault('prompts', {})[item['target']] = final_prompt
                    if studio.MODEL_SPECS[item['target']]['kind']=='video':
                        from backend import camera_movements
                        snapshot=context.get('camera_movement')
                        container=latest.setdefault('scene',{}) if json.loads(item['request'])['body'].get('use_scene') else latest
                        container.setdefault('cameraPromptBasis',{})[item['target']]=camera_movements.basis(snapshot)
                    elif item['operation']!='edit':
                        from backend import frame_composition
                        container=latest.setdefault('scene',{}) if json.loads(item['request'])['body'].get('use_scene') else latest
                        container.setdefault('compositionPromptBasis',{})[item['target']]=frame_composition.basis(context.get('frame_composition'))
                    db.execute('UPDATE projects SET state=?,updated_at=? WHERE id=?', (json.dumps(latest, ensure_ascii=False), studio.now(), item['project_id']))
            else:
                raise HTTPException(409, 'Недопустимый переход этапа')
            db.execute('UPDATE native_chat_jobs SET status=?,prompt=?,message=?,updated_at=? WHERE id=?', (state, final_prompt, body.message, studio.now(), job_id))
            db.execute('UPDATE native_chat_worker SET seen=?,busy=? WHERE id=1', (time.time(), int(state not in {'failed', 'completed'})))
        if item['operation']=='describe_character':
            ctx=json.loads(item['request'])['context']
            studio.production_folders.sync_character(studio,ctx['owner_project_id'],ctx['character_id'])
        else:studio.production_folders.sync_project(studio,item['project_id'])
        return public(row(job_id))

    @app.post('/api/chatgpt/worker/jobs/{job_id}/image')
    async def finish(job_id: str, file: UploadFile = File(...), actual_model: str = Form('not_exposed'), x_studio_worker: str | None = Header(default=None)):
        authenticate(x_studio_worker)
        content = await file.read(20 * 1024 * 1024 + 1)
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(413, 'Оригинал превышает 20 МБ')
        image = studio.inspect_image(content)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            item = db.execute('SELECT * FROM native_chat_jobs WHERE id=?', (job_id,)).fetchone()
            if not item:
                raise HTTPException(404, 'Задание не найдено')
            if item['status'] == 'completed' and item['asset_id']:
                return public(dict(item))
            if item['status'] != 'generating':
                raise HTTPException(409, 'Сначала подготовь промпт; повторной генерации нет')
            aid = uuid.uuid4().hex
            filename = aid + {'PNG': '.png', 'JPEG': '.jpg', 'WEBP': '.webp'}[image['format']]
            studio.LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
            path = studio.LIBRARY_ROOT / filename
            path.write_bytes(content)
            metadata = {**image, 'kind': 'image', 'provider': 'codex_chat', 'requested_model': item['target'],
                        'actual_model': actual_model[:120], 'thread_id': THREAD_ID,
                        'request': {'payload': {'task_type': item['target'], 'input': {'prompt': item['prompt']}}}}
            recipient=json.loads(item['request']).get('context',{}).get('entity')
            if recipient:
                metadata.update(production_node_id=recipient['node_id'],production_entity_snapshot=recipient,character_status='candidate')
                if recipient.get('character_id'):metadata['character_id']=recipient['character_id']
            if item['operation']=='edit':
                request=json.loads(item['request'])
                metadata.update(edit_source_asset_id=request['body']['source_asset_id'],
                                detail_reference_asset_id=request['body']['reference_asset_id'],
                                edit_instruction=request['body']['edit_instruction'],
                                source_provider=request['context']['source_metadata']['provider'],
                                character_id=request['context']['source_metadata'].get('character_id'),
                                character_status='candidate',preservation_contract=PRESERVE_VISUAL)
            db.execute('INSERT INTO library_assets VALUES(?,?,?,?,?,?,?,?)', (aid, job_id, item['project_id'], 0, filename, '', json.dumps(metadata, ensure_ascii=False), studio.now()))
            db.execute("UPDATE native_chat_jobs SET status='completed',asset_id=?,message='Изображение готово; правки — в исходном чате',updated_at=? WHERE id=?", (aid, studio.now(), job_id))
            db.execute('UPDATE native_chat_worker SET seen=?,busy=0 WHERE id=1', (time.time(),))
        studio.production_folders.sync_asset(studio,aid)
        from backend import production_entities
        production_entities.deliver(studio,item,aid)
        return public(row(job_id))
