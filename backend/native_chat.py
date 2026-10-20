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
from backend import character_description, llm_gateway, llm_guard

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


class AgentUsage(BaseModel):
    """Расход токенов, который агент назвал в отчёте о своей работе."""
    input_tokens: int | None = Field(default=None, ge=0, le=10_000_000)
    output_tokens: int | None = Field(default=None, ge=0, le=10_000_000)
    cached_input_tokens: int | None = Field(default=None, ge=0, le=10_000_000)
    reasoning_tokens: int | None = Field(default=None, ge=0, le=10_000_000)


class Progress(BaseModel):
    identity: character_description.Identity | None = None
    status: str
    prompt: str = Field(default='', max_length=20000)
    message: str = Field(default='', max_length=2000)
    provider: str | None = Field(default=None, max_length=60)
    model: str | None = Field(default=None, max_length=120)
    usage: AgentUsage | None = None


def agent_report(body: Progress) -> dict:
    """Отчёт агента о расходе: провайдер, модель и токены — как их назвал агент."""
    report = {'provider': (body.provider or '').strip() or 'unknown',
              'model': (body.model or '').strip() or 'unknown'}
    if body.usage is not None:
        report['usage'] = {'input_tokens': body.usage.input_tokens, 'output_tokens': body.usage.output_tokens,
                           'cached_input_tokens': body.usage.cached_input_tokens,
                           'reasoning_tokens': body.usage.reasoning_tokens}
    return report


def agent_usage(body: Progress):
    """Расход токенов из отчёта агента; None — агент расход не сообщил."""
    if body.usage is None:
        return None
    return llm_gateway.Usage(input_tokens=body.usage.input_tokens, output_tokens=body.usage.output_tokens,
                             cached_input_tokens=body.usage.cached_input_tokens,
                             reasoning_tokens=body.usage.reasoning_tokens)


def insert_agent_call(db, values):
    """Запись вызова агента в журнал вызовов — по именам колонок журнала.

    Одна запись на request_id: повторный отчёт о той же работе денег не удваивает.
    """
    if db.execute('SELECT 1 FROM llm_calls WHERE request_id=?', (values['request_id'],)).fetchone():
        return False
    columns = ','.join(llm_guard.INSERT_COLUMNS)
    marks = ','.join('?' * len(llm_guard.INSERT_COLUMNS))
    db.execute('INSERT INTO llm_calls(' + columns + ') VALUES(' + marks + ')',
               tuple(values[name] for name in llm_guard.INSERT_COLUMNS))
    return True


def agent_context(item) -> str:
    """Контекст задания текстом — по его объёму оценивается работа агента."""
    return json.dumps(json.loads(item['request']).get('context', {}), ensure_ascii=False)


def journal_agent_call(studio, db, item, body: Progress, context_text: str, prompt_text: str, status: str = 'done'):
    """Вызов агента — в тот же журнал вызовов, что и вызовы через шлюз.

    Провайдер и модель — из отчёта агента, а не из константы. Расход, который агент сообщил,
    считается по тарифу реестра; если агент расход не сообщил — списание неизвестно (не ноль):
    работа агента стоила денег, но сколько — неизвестно.

    Тариф 0/0 (подтверждённо бесплатный маршрут) — это тариф: строка получает actual_status='free'
    с фактом 0, отказа нет. Отказ бывает только когда тарифа нет вовсе (записи нет либо цены null) —
    тогда возвращается текст отказа, запись не делается, и вызывающий код переводит задание
    в вынимаемое состояние.
    """
    registry = llm_guard.current_registry()
    provider = (body.provider or '').strip() or None
    model = (body.model or '').strip() or None
    usage = agent_usage(body)
    if not llm_gateway.agent_has_tariff(registry, provider, model):
        return {'refusal': 'Расход агента не посчитан: в реестре нет тарифа.', 'over_limit': False, 'reserve': 0.0}
    actual = llm_gateway.agent_quote(registry, provider, model, usage)
    reference = llm_gateway.agent_reference(registry, provider, model, usage)
    reserve = llm_gateway.agent_reserve(registry, provider, model,
                                        llm_gateway.agent_estimate_usage(context_text, prompt_text))
    # лимит при отчёте считается по реальному тарифу модели агента; перерасход не отменяет запись:
    # деньги уже потрачены — их записывают и показывают в лимите
    over_limit = False
    try:
        llm_guard.check_budget(db, item['project_id'], reserve)
    except HTTPException:
        over_limit = True
    entry = registry.entry(provider, model)
    request_id = item['id'] + '-agent'
    confirmed = actual.status in {'confirmed', 'free'}
    values = {
        'id': uuid.uuid4().hex,
        'request_id': request_id,
        'project_id': item['project_id'],
        'model': model or 'unknown',
        'status': status,
        'usd': actual.cost_usd if confirmed else reserve,
        'estimated_usd': reserve,
        'input_tokens': usage.input_tokens if usage else None,
        'output_tokens': usage.output_tokens if usage else None,
        'created_at': studio.now(),
        'execution_provider': actual.provider,
        'execution_model': actual.model,
        'actual_cost_usd': actual.cost_usd if confirmed else None,
        'actual_status': actual.status,
        'reserved_usd': reserve,
        'billing_source': actual.billing_source,
        'reference_provider': reference.provider if reference else None,
        'reference_model': reference.model if reference else None,
        'reference_kind': reference.kind if reference else None,
        'reference_rate_snapshot_id': llm_guard.snapshot_id(reference.provider or '', reference.model or '',
                                                            reference.rate_as_of or '') if reference else None,
        'reference_cost_usd': reference.cost_usd if reference else None,
        'reference_cost_status': reference.status if reference else None,
        'cached_input_tokens': usage.cached_input_tokens if usage else None,
        'reasoning_tokens': usage.reasoning_tokens if usage else None,
        'price_snapshot_id': llm_guard.snapshot_id(entry.provider, entry.model, entry.as_of) if entry else '',
        'route_mode': 'manual',
        'fallback_from': None,
        'error_kind': None,
        'provider_request_id': None,
    }
    insert_agent_call(db, values)
    return {'refusal': None, 'over_limit': over_limit, 'reserve': reserve}


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
        request = json.dumps({'body': body.model_dump(), 'context': context,
                              'rules': character_description.RULES if body.operation=='describe_character' else studio.system_rules(studio.MODEL_SPECS[body.target]),
                              'quality_request': 'Highest available native quality. For edits keep source dimensions and aspect ratio where supported. Do not upscale or claim an unexposed model/size setting.',
                              'execution':{'intent':body.operation,'prompt_only':body.operation=='prompt','instructions':character_description.RULES if body.operation=='describe_character' else ('PROMPT ONLY. Read the supplied context and structured prompt_base choices. Prepare one coherent finished prompt for the selected model. Preserve reference roles and all explicit framing, lighting and seating constraints. Return it with prompt-ready. Do not call imagegen, generate media, upload images or invoke a paid API. Stop after the prompt is saved.' if body.operation=='prompt' else 'For edit: view each supplied local_path, then call built-in imagegen as an EDIT with referenced_image_paths in the given order. Image 1 is the target; Image 2 is only a detail reference. Follow preservation_contract. Do not recreate from text alone.')}}, ensure_ascii=False, sort_keys=True)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM native_chat_jobs WHERE id=?', (body.request_id,)).fetchone()
            if existing:
                if existing['request'] != request:
                    raise HTTPException(409, 'Этот ID уже принадлежит другому запросу')
                return public(dict(existing))
            # работа агента — тоже платный вызов: тариф и лимит проверяются до постановки задания
            registry = llm_guard.current_registry()
            if not llm_gateway.agent_has_tariff(registry, None, None):
                raise HTTPException(400, 'Для работы агента нет тарифа: добавь модель и цены в реестр шлюза')
            estimate = llm_gateway.agent_reserve(registry, None, None,
                                                 llm_gateway.agent_estimate_usage(request, ''))
            llm_guard.check_budget(db, body.project_id, estimate)
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
            llm_guard.ensure_schema(db)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            item = db.execute('SELECT * FROM native_chat_jobs WHERE id=?', (job_id,)).fetchone()
            if not item:
                raise HTTPException(404, 'Задание не найдено')
            if item['status'] not in {'preparing', 'generating'}:
                raise HTTPException(409, 'Задание больше не выполняется')
            final_prompt = body.prompt.strip() or item['prompt']
            refusal = None
            over_limit = False
            if body.status == 'failed':
                state = 'failed'
                # отчёт о неуспехе журналируется по тем же правилам: потраченные деньги не теряются
                charge = journal_agent_call(studio, db, item, body, agent_context(item), final_prompt, status='failed')
                refusal = charge['refusal']
                over_limit = charge['over_limit']
            elif item['operation']=='describe_character' and item['status']=='preparing' and body.status=='identity_ready' and body.identity is not None:
                result=character_description.apply(db,studio,item,body.identity)
                final_prompt=json.dumps(result,ensure_ascii=False);state='completed'
            elif item['operation']!='describe_character' and item['status'] == 'preparing' and body.status == 'prompt_ready' and final_prompt:
                state = 'generating' if item['operation'] in {'generate','edit'} else 'completed'
                if item['operation']=='edit':final_prompt=PRESERVE_VISUAL+'\n\nREQUESTED CHANGE:\n'+final_prompt
                studio.validate_prompt(item['target'], final_prompt, len(json.loads(item['request'])['context']['references']))
                context = json.loads(item['request'])['context']
                # расход агента — в тот же журнал и в той же транзакции: либо запись есть, либо задание не выполнено
                charge = journal_agent_call(studio, db, item, body, json.dumps(context, ensure_ascii=False), final_prompt)
                refusal = charge['refusal']
                over_limit = charge['over_limit']
                if refusal:
                    # тарифа нет: работа не засчитывается, но задание переходит в вынимаемое состояние
                    state = 'failed'
                else:
                    report = agent_report(body)
                    db.execute('INSERT INTO prompt_versions VALUES(?,?,?,?,?,?,?,?,?,?)',
                               (uuid.uuid4().hex, item['project_id'], item['target'], final_prompt, json.dumps(context, ensure_ascii=False), 'codex_chat', report['model'], json.dumps(report, ensure_ascii=False), studio.RULES_VERSION, studio.now()))
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
            message = body.message
            if refusal:
                message = 'Отчёт агента отвергнут: ' + refusal
            elif over_limit:
                message = (message + ' ' if message else '') + 'Лимит превышен: расход агента записан и занимает лимит.'
            db.execute('UPDATE native_chat_jobs SET status=?,prompt=?,message=?,updated_at=? WHERE id=?', (state, final_prompt, message, studio.now(), job_id))
            db.execute('UPDATE native_chat_worker SET seen=?,busy=? WHERE id=1', (time.time(), int(state not in {'failed', 'completed'})))
        if refusal:
            raise HTTPException(400, refusal)
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
