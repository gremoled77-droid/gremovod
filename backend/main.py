"""Local AI Workflow Studio API. Credentials are read server-side, never returned to UI."""
import json, os, sqlite3, uuid, re, subprocess, shutil, asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from contextlib import contextmanager
import httpx
from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
from backend.connections import router as connections_router, credential, provider_key
from backend.image_assets import download_image, inspect_image, output_urls, download_video
from backend.prompt_rules import RULES_VERSION, system_rules, PROFILES, reference_label, validate_prompt
from backend.model_catalog import MODEL_SPECS, ALLOWED_CHAT, IMAGE_TASKS, VIDEO_MODELS
from backend import adapters
from backend import camera_movements
from backend import frame_composition

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ['STUDIO_DATA_DIR']).resolve() if os.environ.get('STUDIO_DATA_DIR') else None  # облачный режим: все данные в одном томе
if DATA:DATA.mkdir(parents=True,exist_ok=True)
PRODUCTIONS_ROOT=(DATA or ROOT.parent)/'projects'
LOCAL_MEDIA_BIN=ROOT.parent/'tools'/'ffmpeg'/'bin'
if LOCAL_MEDIA_BIN.is_dir():
    os.environ['PATH']=str(LOCAL_MEDIA_BIN)+os.pathsep+os.environ.get('PATH','')
DB=(DATA or ROOT)/'studio.sqlite3'
MEDIA=(DATA or ROOT)/'media'
MEDIA.mkdir(exist_ok=True)
BASE='https://api.piapi.ai'
PIAPI_KEY_FILE=ROOT.parent/'PIAPI_API_KEY.txt'
app=FastAPI(title='AI Workflow Studio', version='0.3.0')
app.include_router(connections_router)
app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:5173','http://localhost:5173'],allow_methods=['*'],allow_headers=['*'])

@contextmanager
def connect():
    db=sqlite3.connect(DB,timeout=10)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()

@app.on_event('startup')
def init():
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, title TEXT NOT NULL, state TEXT NOT NULL, updated_at TEXT NOT NULL)')
        if 'revision' not in {r['name'] for r in db.execute('PRAGMA table_info(projects)')}:
            db.execute('ALTER TABLE projects ADD COLUMN revision INTEGER NOT NULL DEFAULT 0')
        db.execute('''CREATE TRIGGER IF NOT EXISTS project_revision AFTER UPDATE OF state,title ON projects
                      BEGIN UPDATE projects SET revision=OLD.revision+1 WHERE id=NEW.id; END''')
        db.execute('CREATE TABLE IF NOT EXISTS prompt_versions(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,target TEXT NOT NULL,prompt TEXT NOT NULL,context TEXT NOT NULL,provider TEXT NOT NULL,model TEXT NOT NULL,usage TEXT NOT NULL,rules_version TEXT NOT NULL,created_at TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS generation_approvals(job_id TEXT PRIMARY KEY,estimated_usd REAL,max_cost_usd REAL,approved_at TEXT,price_basis TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS library_assets(id TEXT PRIMARY KEY,job_id TEXT NOT NULL,project_id TEXT NOT NULL,output_index INTEGER NOT NULL,filename TEXT NOT NULL,source_url TEXT NOT NULL,metadata TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(job_id,output_index))')
        db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, project_id TEXT, kind TEXT, provider TEXT, task_id TEXT, status TEXT, request TEXT, response TEXT, created_at TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS character_assets (id TEXT PRIMARY KEY, project_id TEXT, character_id TEXT NOT NULL, category TEXT NOT NULL, model_id TEXT, filename TEXT NOT NULL, original_name TEXT NOT NULL, external_url TEXT, note TEXT, created_at TEXT NOT NULL)')

def now(): return datetime.now(timezone.utc).isoformat()

class Project(BaseModel):
    id:str|None=None
    title:str='Новый проект'
    state:dict[str,Any]=Field(default_factory=dict)
    base_revision:int|None=Field(default=None,ge=0)

@app.get('/api/health')
def health(): return {'ok':True,'version':'0.3.0','mode':'local'}

@app.get('/api/projects')
def projects():
    with connect() as db: return [dict(x) for x in db.execute('SELECT id,title,updated_at FROM projects ORDER BY updated_at DESC')]

@app.get('/api/projects/{pid}')
def project(pid:str):
    with connect() as db: x=db.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
    if not x: raise HTTPException(404,'Проект не найден')
    return {'id':x['id'],'title':x['title'],'state':production_folders.shared_characters(sys.modules[__name__],pid,json.loads(x['state'])),'updated_at':x['updated_at'],'revision':x['revision']}

@app.post('/api/projects')
def save_project(p:Project):
    pid=p.id or str(uuid.uuid4())
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        existing=db.execute('SELECT revision FROM projects WHERE id=?',(pid,)).fetchone()
        if existing and p.base_revision!=existing['revision']:
            raise HTTPException(409,{'code':'PROJECT_CONFLICT','message':'Проект изменён в другом окне или обработчиком. Локальные правки не сохранены поверх новой версии.','revision':existing['revision']})
        if not existing and p.base_revision is not None:raise HTTPException(409,'Исходная версия проекта отсутствует')
        db.execute('INSERT INTO projects(id,title,state,updated_at) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,state=excluded.state,updated_at=excluded.updated_at',(pid,p.title,json.dumps(p.state,ensure_ascii=False),now()))
        revision=db.execute('SELECT revision FROM projects WHERE id=?',(pid,)).fetchone()['revision']
    production_folders.sync_project(sys.modules[__name__],pid)
    return {'id':pid,'saved':True,'revision':revision}

class ChatRequest(BaseModel):
    model:str='gpt-5.6-luna'
    messages:list[dict[str,Any]]

class TaskRequest(BaseModel):
    project_id:str|None=None
    kind:str='image'
    payload:dict[str,Any]

def get_key(header:str|None):
    return credential('piapi',header,PIAPI_KEY_FILE)[0]

def up_error(response:httpx.Response):
    if response.status_code==403 and ('1010' in response.text or 'browser_signature_banned' in response.text):
        raise HTTPException(403,{'code':'PIAPI_CLOUDFLARE_1010','message':'Cloudflare PiAPI блокирует клиент. Обратись в поддержку PiAPI. Автоматических повторов нет.'})
    raise HTTPException(response.status_code,{'message':f'PiAPI вернул HTTP {response.status_code}. Проверь доступ и параметры; повторный запуск требует проверки очереди.'})

async def request_piapi(method:str,path:str,key:str,payload:dict|None=None):
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r=await client.request(method,BASE+path,headers={'X-API-KEY':key,'Content-Type':'application/json'},json=payload)
    except httpx.RequestError as e: raise HTTPException(502,f'Не удалось соединиться с PiAPI: {type(e).__name__}')
    if r.is_error: up_error(r)
    try: value=r.json()
    except ValueError: raise HTTPException(502,'PiAPI вернул не-JSON ответ')
    if not isinstance(value,dict) or value.get('code',200) not in (0,200): raise HTTPException(502,'PiAPI вернул неожиданный ответ; проверь историю задач перед повторной оплатой')
    return value

class UnifiedChatRequest(BaseModel):
    provider:str='openai'
    model:str='gpt-4.1-mini'
    messages:list[dict[str,Any]]=Field(min_length=1,max_length=50)

@app.post('/api/llm/chat')
async def unified_chat(body:UnifiedChatRequest, x_api_key:str|None=Header(default=None)):
    key=get_key(x_api_key) if body.provider=='piapi' else provider_key(body.provider,x_api_key)
    if not key or not key.isascii() or any(c.isspace() for c in key):
        raise HTTPException(400,'Введи корректный API-ключ выбранного провайдера')
    if body.provider not in {'openai','piapi'}: raise HTTPException(400,'Недопустимый провайдер')
    messages=[{'role':m.get('role'),'content':str(m.get('content',''))[:20000]} for m in body.messages if m.get('role') in {'user','system','assistant'}]
    if not messages: raise HTTPException(400,'Нет сообщений')
    system='\n'.join(m['content'] for m in messages if m['role']=='system') or 'You are an AI production assistant.'
    history=[m for m in messages if m['role']!='system']
    if body.provider=='openai':
        content,usage=await agent_completion('openai',body.model,key,system,json.dumps(history,ensure_ascii=False))
        return {'choices':[{'message':{'role':'assistant','content':content}}],'usage':usage,'provider':'openai'}
    if body.model not in ALLOWED_CHAT: raise HTTPException(400,'Модель PiAPI отсутствует в списке')
    return await request_piapi('POST','/v1/chat/completions',key,{'model':body.model,'messages':messages})

class DiagnosticInfo(BaseModel):
    check_remote:bool=False

@app.get('/api/diagnostics')
def diagnostics():
    return {'python':__import__('sys').version.split()[0], 'ffmpeg':bool(shutil.which('ffmpeg')),
            'ffprobe':bool(shutil.which('ffprobe')), 'sqlite':sqlite3.sqlite_version,
            'database_writable':os.access(DB.parent,os.W_OK),'piapi_base':BASE,
            'warning':'Удалённые API не проверяются; Cloudflare 1010 требует обращения в поддержку PiAPI.'}

@app.post('/api/chat')
async def chat(body:ChatRequest,x_api_key:str|None=Header(default=None)):
    if body.model not in ALLOWED_CHAT: raise HTTPException(400,'Неизвестная модель GPT')
    if not body.messages or len(body.messages)>50: raise HTTPException(400,'Ожидалось 1–50 сообщений')
    return await request_piapi('POST','/v1/chat/completions',get_key(x_api_key),body.model_dump())

@app.post('/api/tasks')
async def create_task(req:TaskRequest,x_api_key:str|None=Header(default=None)):
    raise HTTPException(410,'Прямой запуск отключён. Используй /api/model-jobs с подтверждением стоимости.')

@app.get('/api/jobs/{job_id}')
async def job_status(job_id:str,x_api_key:str|None=Header(default=None)):
    with connect() as db: job=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
    if not job: raise HTTPException(404,'Задание не найдено')
    if job['status'] in {'completed','failed','submission_unknown'} or not job['task_id']: return {'job_id':job_id,'upstream':json.loads(job['response'])}
    result=await request_piapi('GET','/api/v1/task/'+job['task_id'],get_key(x_api_key))
    status=(result.get('data') or {}).get('status','unknown')
    with connect() as db: db.execute('UPDATE jobs SET status=?,response=? WHERE id=?',(status,json.dumps(result,ensure_ascii=False),job_id))
    return {'job_id':job_id,'upstream':result}

@app.get('/api/jobs')
def jobs(project_id:str|None=None):
    with connect() as db:
        rows=db.execute('SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC',(project_id,)) if project_id else db.execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT 100')
        delivery={d['job_id']:dict(d) for d in db.execute('SELECT * FROM job_delivery')}
        return [{'id':x['id'],'kind':x['kind'],'provider':x['provider'],'task_id':x['task_id'],'status':x['status'],'response':json.loads(x['response']),'delivery':delivery.get(x['id'])} for x in rows]

@app.get('/api/prompt-knowledge')
def prompt_knowledge():
    path=ROOT.parent/'docs'/'official-prompts'/'manifest.json'
    sources=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
    return {'version':RULES_VERSION,'profiles':PROFILES,'sources':sources}

@app.get('/api/model-specs')
def model_specs():
    return MODEL_SPECS

class ComposeRequest(BaseModel):
    project_id:str
    model:str='gpt-5.6-luna'
    provider:str='piapi'
    target:str
    approved:bool=False
    use_scene:bool=False

class PromptDraftRequest(BaseModel):
    brief:str=Field(min_length=1,max_length=12000)
    target:str
    character:dict[str,Any]|None=None
    style:dict[str,str]=Field(default_factory=dict)
    camera:dict[str,Any]|None=None
    composition:dict[str,Any]|None=None
    motion_brief:str=Field(default='',max_length=12000)

@app.post('/api/prompt-drafts')
def prompt_draft(body:PromptDraftRequest):
    spec=MODEL_SPECS.get(body.target)
    if not spec: raise HTTPException(400,'Модель отсутствует в каталоге')
    character=body.character or {}
    profile=(character.get('profiles') or {}).get(body.target,{})
    sections=[f'Черновик для {body.target}. Проверь текст перед запуском.',body.brief]
    if spec['kind']=='image':
        composition=frame_composition.context(body.composition)
        if composition:sections.append('Frame and light: '+composition['instruction'])
    if spec['kind']=='video':
        if body.motion_brief.strip():sections.append('Действие в кадре: '+body.motion_brief.strip())
        camera=camera_movements.context(body.camera)
        if camera:sections.append('Camera movement: '+camera['instruction'])
    identity=character.get('identity') or {}
    traits='\n'.join(f'{k}: {v}' for k,v in identity.items() if v)
    if traits: sections.append('Канон персонажа (сохранять без изменений):\n'+traits)
    if body.style: sections.append('Библия мира:\n'+'\n'.join(f'{k}: {v}' for k,v in body.style.items() if v))
    if profile.get('prompt_notes'): sections.append('Инструкции для этой модели:\n'+str(profile['prompt_notes']))
    if profile.get('reference_urls'): sections.append('Референсы профиля для ручной проверки:\n'+str(profile['reference_urls']))
    sections.append('Движение: отдельно уточни действия героя, движение камеры и порядок событий.' if spec['kind']=='video' else 'Статичный кадр: уточни композицию, ракурс и освещение.')
    return {'prompt':'\n\n'.join(sections),'target':body.target,'mode':'local_draft','external_calls':0}

def compose_context(body:ComposeRequest):
    spec=MODEL_SPECS.get(body.target)
    if not spec: raise HTTPException(400,'Модель отсутствует в каталоге')
    state=project(body.project_id)['state']
    scene=state.get('scene',{}) if body.use_scene else {}
    brief=(scene.get('brief','') if body.use_scene else state.get('brief','')).strip()
    if not brief: raise HTTPException(400,'Заполни режиссёрское задание')
    char=next((c for c in state.get('characters',[]) if c.get('id')==state.get('selectedCharacter')), {})
    profile=(char.get('profiles') or {}).get(body.target,{})
    refs=[]
    manual=[] if body.use_scene else ([state.get('videoReference','')] if spec['kind']=='video' else re.split(r'[\n,]',state.get('referenceUrls','')))
    for ref in [*manual,*re.split(r'[\n,]',profile.get('reference_urls',''))]:
        if ref.strip() and ref.strip() not in refs: refs.append(ref.strip())
    references=[]
    if body.use_scene:
        for asset in scene.get('assets',[]):
            with connect() as db:
                row=production_folders.accessible_asset(sys.modules[__name__],db,asset.get('asset_id'),body.project_id)
            if not row: raise HTTPException(400,'Исходник сцены отсутствует в библиотеке этого проекта')
            metadata=json.loads(row['metadata'])
            if metadata.get('kind') in {'video','audio'}: raise HTTPException(400,'В этой версии сцены принимают изображения')
            references.append({'label':reference_label(body.target,len(references)+1),'asset_id':row['id'],
                               'url':reference_upload.reference_url(sys.modules[__name__],row),'local_path':str((LIBRARY_ROOT/row['filename']).resolve()),
                               'role':asset.get('role','reference'),'note':str(asset.get('note',''))[:2000]})
    for ref in refs:
        references.append({'label':reference_label(body.target,len(references)+1),'url':ref})
    if body.provider=='codex_chat' and char and not body.use_scene:
        char_owner=production_folders.character_owner(sys.modules[__name__],body.project_id,char['id'])
        with connect() as db:
            assets=db.execute("SELECT * FROM character_assets WHERE project_id=? AND character_id=? AND (category IN ('real_references','approved_generations') OR (category='model_references' AND model_id=?)) ORDER BY created_at,id",(char_owner,char['id'],body.target)).fetchall()
        if char.get('working_asset_id'):
            with connect() as db:
                working=production_folders.accessible_asset(sys.modules[__name__],db,char['working_asset_id'],body.project_id)
            if not working:raise HTTPException(400,'Рабочий образ персонажа отсутствует')
            working_path=(LIBRARY_ROOT/working['filename']).resolve()
            if not working_path.is_relative_to(LIBRARY_ROOT.resolve()) or not working_path.is_file():raise HTTPException(400,'Файл рабочего образа отсутствует')
            references.append({'label':reference_label(body.target,len(references)+1),'asset_id':working['id'],'local_path':str(working_path),'role':'approved_character_reference','note':'Current working character appearance. This image takes priority over older textual appearance descriptions.','url':working['source_url']})
            assets=[a for a in assets if a['category']=='model_references']
        for asset in assets:
            path=char_directory(char_owner,char['id'],asset['category'],asset['model_id'] or '')/asset['filename']
            if not path.is_file():raise HTTPException(400,'Исходник персонажа отсутствует на диске')
            references.append({'label':reference_label(body.target,len(references)+1),'asset_id':asset['id'],
                               'local_path':str(path.resolve()),'role':'approved_character_reference' if asset['category']=='approved_generations' else 'character_identity',
                               'note':asset['note'],'url':asset['external_url'] or ''})
    if len(references)>spec['max_refs']: raise HTTPException(400,'Превышено число референсов модели')
    anchor=None
    if state.get('videoAssetId') and spec['kind']=='video':
        with connect() as db: row=db.execute('SELECT metadata FROM library_assets WHERE id=? AND project_id=?',(state['videoAssetId'],body.project_id)).fetchone()
        if row: anchor=json.loads(row['metadata'])
    return {'brief':brief,'motion_brief':state.get('motionBrief','') if spec['kind']=='video' else '',
            'camera_movement':camera_movements.context(state.get('camera')) if spec['kind']=='video' else None,'target_model':body.target,
            'frame_composition':frame_composition.context(state.get('composition')) if spec['kind']=='image' else None,
            'character_identity':char.get('identity',{}),'model_specific_character_profile':profile,
            'world_bible':state.get('style',{}),'settings':state.get('parameters',{}).get(body.target,{}),
            'references':references,'scene':{k:scene[k] for k in ('brief','assets') if k in scene},
            'selected_image_metadata':anchor,'capabilities':spec,'rules_version':RULES_VERSION}

@app.post('/api/compose/preview')
def compose_preview(body:ComposeRequest):
    context=compose_context(body)
    return {'context':context,'system_rules':system_rules(MODEL_SPECS[body.target]),'external_calls':0}

@app.post('/api/compose')
async def compose(body:ComposeRequest, x_api_key:str|None=Header(default=None)):
    context=compose_context(body)
    if not body.approved: raise HTTPException(400,'Нужно подтверждение платного LLM-запроса')
    if body.provider=='piapi' and body.model not in ALLOWED_CHAT: raise HTTPException(400,'Недопустимая LLM-модель PiAPI')
    if body.provider not in {'piapi','openai'}: raise HTTPException(400,'Неизвестный LLM-провайдер')
    key=get_key(x_api_key) if body.provider=='piapi' else provider_key('openai',x_api_key)
    content,usage=await agent_completion(body.provider,body.model,key,system_rules(MODEL_SPECS[body.target]),json.dumps(context,ensure_ascii=False))
    if not content.strip(): raise HTTPException(502,'LLM вернула пустой промпт')
    try: validate_prompt(body.target,content,len(context['references']))
    except HTTPException as exc: raise HTTPException(502,exc.detail)
    for index in re.findall(r'@image(\d+)',content,re.IGNORECASE):
        if not 1<=int(index)<=len(context['references']): raise HTTPException(502,'LLM сослалась на отсутствующее изображение; платный повтор автоматически не выполняется')
    version_id=uuid.uuid4().hex
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO prompt_versions VALUES(?,?,?,?,?,?,?,?,?,?)',(version_id,body.project_id,body.target,content,json.dumps(context,ensure_ascii=False),body.provider,body.model,json.dumps(usage),RULES_VERSION,now()))
        # Merge into the latest project so unrelated edits are not overwritten by a slow LLM.
        row=db.execute('SELECT state FROM projects WHERE id=?',(body.project_id,)).fetchone()
        current=json.loads(row['state'])
        current.setdefault('prompts',{})[body.target]=content
        db.execute('UPDATE projects SET state=?,updated_at=? WHERE id=?',(json.dumps(current,ensure_ascii=False),now(),body.project_id))
    return {'prompt':content,'usage':usage,'version_id':version_id,'rules_version':RULES_VERSION,'references':context['references']}

@app.get('/api/projects/{project_id}/prompt-versions')
def prompt_versions(project_id:str):
    project(project_id)
    with connect() as db: rows=db.execute('SELECT id,target,prompt,provider,model,usage,rules_version,created_at FROM prompt_versions WHERE project_id=? ORDER BY created_at DESC',(project_id,)).fetchall()
    return [dict(row) for row in rows]

class ModelJobRequest(BaseModel):
    project_id:str|None=None
    model_id:str
    prompt:str=Field(min_length=1)
    options:dict[str,Any]=Field(default_factory=dict)
    reference_urls:list[str]=Field(default_factory=list)
    approved:bool=False
    max_cost_usd:float=Field(default=0,ge=0,le=100,allow_inf_nan=False)
    request_id:str|None=None
    quote_token:str=''
    node_id:str|None=Field(default=None,max_length=100)

def image_payload(body:ModelJobRequest,enforce_launch:bool=True):
    spec=MODEL_SPECS.get(body.model_id)
    if not spec: raise HTTPException(400,'Модель отсутствует в каталоге')
    if enforce_launch and not spec.get('launch_enabled'): raise HTTPException(400,'Запуск этой модели отключён до проверки схемы и стоимости.')
    if not body.prompt.strip(): raise HTTPException(400,'Промпт не может быть пустым')
    if len(body.reference_urls)>spec['max_refs']: raise HTTPException(400,'Превышено число референсов')
    from urllib.parse import urlsplit
    for ref in body.reference_urls:
        parsed=urlsplit(ref)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.hostname in {'localhost','127.0.0.1','::1'}:
            raise HTTPException(400,'Нужен публичный HTTPS URL референса; локальный файл нельзя передать провайдеру напрямую')
    is_video=spec['kind']=='video'
    if is_video:
        from backend import production_entities
        production_entities.video_anchor(sys.modules[__name__],body.project_id,body.reference_urls)
    if adapters.handles(spec): return adapters.build(spec,body)
    if spec.get('adapter')=='hunyuan_i2v':
        if body.options:raise HTTPException(400,'В этом тестовом адаптере Hunyuan используются длительность и разрешение провайдера по умолчанию')
        if len(body.reference_urls)!=1:raise HTTPException(400,'Hunyuan I2V требует один исходный кадр')
        if re.search(r'@(image|video|audio)\d+',body.prompt,re.I):raise HTTPException(400,'Для Hunyuan нужен обычный текст без тегов Seedance')
        return {'model':spec['model'],'task_type':spec['task_type'],
                'input':{'prompt':body.prompt,'image':body.reference_urls[0]}}
    allowed={'resolution','duration','aspect_ratio'} if is_video else {'size','aspect_ratio','output_format'}
    if set(body.options)-allowed: raise HTTPException(400,'Неподдерживаемый параметр модели')
    options={}
    for key,value in body.options.items():
        if is_video and key=='duration':
            if type(value) is not int or not spec['duration_min']<=value<=spec['duration_max']: raise HTTPException(400,'Длительность должна быть целым числом от 4 до 30 секунд')
            options[key]=value
            continue
        if not isinstance(spec.get(key),list) or value not in spec[key]: raise HTTPException(400,'Недопустимый параметр '+key)
        options[key]=value
    if not spec.get('launch_enabled'): raise HTTPException(400,'Запуск этой модели отключён до проверки схемы и стоимости. Доступен Seedream 5 Lite.')
    # One image only; batch parameters cannot enter through options.
    options=({'resolution':'480p','duration':5,'aspect_ratio':'16:9',**options} if is_video else {'size':'2K','aspect_ratio':'1:1','output_format':'png',**options})
    if is_video:
        if re.search(r'@(video|audio)\d+',body.prompt,re.IGNORECASE): raise HTTPException(400,'Этот адаптер принимает только изображения; video/audio references ещё не подключены')
        for index in re.findall(r'@image(\d+)',body.prompt,re.IGNORECASE):
            if not 1<=int(index)<=len(body.reference_urls): raise HTTPException(400,'В промпте указан отсутствующий референс')
        options['mode']='omni_reference' if body.reference_urls else 'text_to_video'
        if body.reference_urls: options['omni_reference_task_type']='reference'
    payload={'model':spec['model'],'task_type':spec['task_type'],'input':{'prompt':body.prompt,**options}}
    if body.reference_urls: payload['input'][spec['ref_field']]=body.reference_urls
    return payload

def generation_cost(body,payload):
    spec=MODEL_SPECS[body.model_id]
    if adapters.handles(spec): return adapters.cost(spec,payload)
    if spec['kind']=='video' and 'price_per_second_usd' in spec: return round(spec['price_per_second_usd'][payload['input']['resolution']]*payload['input']['duration'],3)
    return spec['price_usd']

@app.post('/api/model-jobs/estimate')
def estimate_image(body:ModelJobRequest):
    payload=image_payload(body)
    cost=generation_cost(body,payload)
    if not body.project_id:raise HTTPException(400,'Сначала сохрани проект')
    project(body.project_id)
    return {'quote_token':security.quote(body.project_id,payload,cost),'expires_in_seconds':600,'model_id':body.model_id,'kind':MODEL_SPECS[body.model_id]['kind'],'estimated_usd':cost,'images':0 if MODEL_SPECS[body.model_id]['kind']=='video' else 1,'payload':payload,
            'source':MODEL_SPECS[body.model_id]['docs'],'verified_at':MODEL_SPECS[body.model_id].get('verified_at','2026-10-15'),
            'note':'Оценка по документации провайдера; фактическое списание определяется PiAPI. Лимит относится к одному запуску.'}

@app.post('/api/model-jobs/preview')
def preview_model_job(body:ModelJobRequest):
    """Сухой прогон: параметры, тело запроса и цена без сетевых вызовов. Работает и для непроверенных моделей."""
    spec=MODEL_SPECS.get(body.model_id)
    if not spec: raise HTTPException(400,'Модель отсутствует в каталоге')
    payload=image_payload(body,enforce_launch=False)
    cost=generation_cost(body,payload)
    return {'model_id':body.model_id,'kind':spec['kind'],'launch_enabled':bool(spec.get('launch_enabled')),
            'verified_at':spec.get('verified_at'),'path':adapters.submit_path(spec),
            'wire_body':adapters.wire_body(spec,payload),'estimated_usd':cost,'external_calls':0,
            'note':'Сухой прогон. Запуск выключен, пока параметры и цена не проверены реальным вызовом.' if not spec.get('launch_enabled') else 'Сухой прогон.'}

@app.post('/api/model-jobs')
async def model_job(body:ModelJobRequest,x_api_key:str|None=Header(default=None)):
    payload=image_payload(body)
    if not body.project_id: raise HTTPException(400,'Сначала сохрани проект')
    project(body.project_id)
    if not body.request_id or not re.fullmatch(r'[a-zA-Z0-9_-]{16,100}',body.request_id): raise HTTPException(400,'Нужен уникальный request_id')
    request_data=json.dumps({'project_id':body.project_id,'model_id':body.model_id,'payload':payload,**({'node_id':body.node_id} if body.node_id else {})},ensure_ascii=False,sort_keys=True)
    with connect() as db:
        previous=db.execute('SELECT * FROM jobs WHERE id=?',(body.request_id,)).fetchone()
    if previous:
        if previous['request']!=request_data: raise HTTPException(409,'Этот request_id уже использован с другими параметрами')
        return {'job_id':previous['id'],'status':previous['status'],'upstream':json.loads(previous['response']),'duplicate':True}
    cost=generation_cost(body,payload)
    if not body.approved or body.max_cost_usd<cost: raise HTTPException(400,f'Подтверди платный запуск и лимит не меньше ${cost:.3f}')
    security.verify_quote(body.quote_token,body.project_id,payload,cost)
    key=get_key(x_api_key)
    jid=body.request_id
    # Reserve before upstream I/O. Never retry a submission with an uncertain result.
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        security.check_budget(db,body.project_id,cost)
        try:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',(jid,body.project_id,MODEL_SPECS[body.model_id]['kind'],'piapi',None,'submitting',request_data,'{}',now()))
            db.execute('INSERT INTO generation_approvals VALUES(?,?,?,?,?)',(jid,cost,body.max_cost_usd,now(),'documentation_estimate'))
        except sqlite3.IntegrityError: raise HTTPException(409,'Заявка уже отправляется; обнови очередь')
    try:
        spec=MODEL_SPECS[body.model_id]
        result=await request_piapi('POST',adapters.submit_path(spec),key,adapters.wire_body(spec,payload))
        task=result.get('data') or {}
        if not isinstance(task,dict) or not task.get('task_id'):
            raise HTTPException(502,'Провайдер не вернул task_id. Не повторяй оплату; проверь историю PiAPI.')
        status=str(task.get('status','submitted'))
        with connect() as db:
            db.execute('UPDATE jobs SET task_id=?,status=?,response=? WHERE id=?',(task['task_id'],status,json.dumps(result,ensure_ascii=False),jid))
    except HTTPException as exc:
        status='submission_unknown' if exc.status_code>=500 else 'failed'
        with connect() as db: db.execute('UPDATE jobs SET status=?,response=? WHERE id=?',(status,json.dumps({'detail':exc.detail},ensure_ascii=False),jid))
        raise HTTPException(exc.status_code,{'job_id':jid,'status':status,'message':exc.detail})
    return {'job_id':jid,'upstream':result,'status':status}


# Character library: project / character / references, approved, rejected, per-model.
CHAR_ROOT=(DATA or ROOT)/'character_library'
CHAR_ROOT.mkdir(exist_ok=True)
CHAR_CATEGORIES={'real_references','approved_generations','rejected_generations','model_references','candidate_generations','archived_generations'}
CHAR_EXTS={'.png','.jpg','.jpeg','.webp'}
SAFE_ID=re.compile(r'^[a-zA-Z0-9_-]{1,100}$')
def checked_id(value:str):
    if not SAFE_ID.fullmatch(value): raise HTTPException(400,'Неверный идентификатор папки')
    return value

def char_directory(project_id:str,character_id:str,category:str,model_id:str=''):
    checked_id(project_id);checked_id(character_id)
    if category not in CHAR_CATEGORIES: raise HTTPException(400,'Неизвестная категория')
    directory=CHAR_ROOT/project_id/character_id/category
    if category=='model_references':
        if model_id not in MODEL_SPECS:raise HTTPException(400,'Модель профиля отсутствует в каталоге')
        directory=directory/model_id
    return directory

@app.get('/api/characters/{project_id}/{character_id}/assets')
def list_character_assets(project_id:str,character_id:str):
    checked_id(project_id);checked_id(character_id)
    project_id=production_folders.character_owner(sys.modules[__name__],project_id,character_id)
    with connect() as db:
        rows=db.execute('SELECT * FROM character_assets WHERE project_id=? AND character_id=? ORDER BY created_at DESC',(project_id,character_id)).fetchall()
    return [{**dict(row),'url':f'/api/character-assets/{row["id"]}'} for row in rows]

@app.post('/api/characters/{project_id}/{character_id}/assets')
async def upload_character_asset(project_id:str, character_id:str, file:UploadFile=File(...), category:str=Form('real_references'), model_id:str=Form(''),note:str=Form(''),external_url:str=Form('')):
    project_id=production_folders.character_owner(sys.modules[__name__],project_id,character_id)
    directory=char_directory(project_id,character_id,category,model_id)
    ext=Path(file.filename or '').suffix.lower()
    if ext not in CHAR_EXTS: raise HTTPException(415,'Загружай PNG, JPEG или WebP')
    content=await file.read(20*1024*1024+1)
    if len(content)>20*1024*1024:raise HTTPException(413,'Лимит 20 МБ на изображение')
    inspect_image(content)
    if external_url and not external_url.startswith('https://'):raise HTTPException(400,'Внешняя ссылка должна начинаться с https://')
    directory.mkdir(parents=True,exist_ok=True)
    aid=uuid.uuid4().hex
    filename=aid+ext
    (directory/filename).write_bytes(content)
    with connect() as db:
        db.execute('INSERT INTO character_assets VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,project_id,character_id,category,model_id if category=='model_references' else '',filename,(file.filename or '')[:200],external_url[:2048],note[:2000],now()))
    production_folders.sync_character(sys.modules[__name__],project_id,character_id)
    return {'id':aid,'url':f'/api/character-assets/{aid}','category':category,'model_id':model_id,'external_url':external_url}

@app.get('/api/character-assets/{asset_id}')
def read_character_asset(asset_id:str):
    checked_id(asset_id)
    with connect() as db: row=db.execute('SELECT * FROM character_assets WHERE id=?',(asset_id,)).fetchone()
    if not row:raise HTTPException(404,'Изображение не найдено')
    directory=char_directory(row['project_id'],row['character_id'],row['category'],row['model_id'] or '')
    path=directory/row['filename']
    if not path.is_file():raise HTTPException(404,'Файл отсутствует на диске')
    return FileResponse(path)

@app.delete('/api/character-assets/{asset_id}')
def delete_character_asset(asset_id:str):
    checked_id(asset_id)
    with connect() as db:
        row=db.execute('SELECT * FROM character_assets WHERE id=?',(asset_id,)).fetchone()
        if not row:raise HTTPException(404,'Файл не найден')
        directory=char_directory(row['project_id'],row['character_id'],row['category'],row['model_id'] or '')
        (directory/row['filename']).unlink(missing_ok=True)
        db.execute('DELETE FROM character_assets WHERE id=?',(asset_id,))
    return {'deleted':True}

# Local authorized-source Audio Lab. We intentionally do not bypass video platforms' controls.
ALLOWED_MEDIA={'.mp3','.wav','.m4a','.aac','.ogg','.flac','.mp4','.mov','.webm','.mkv'}
def cmd(args:list[str]):
    if not shutil.which(args[0]): raise HTTPException(503,f'Не установлен {args[0]} — установи FFmpeg')
    try:
        return subprocess.run(args,capture_output=True,text=True,timeout=120,check=True)
    except subprocess.CalledProcessError as exc:
        raise HTTPException(422,{'error':'FFmpeg: не удалось обработать медиа','detail':exc.stderr[-600:]})
    except subprocess.TimeoutExpired: raise HTTPException(504,'Слишком долгий медиафайл')

@app.post('/api/media/upload')
async def upload_media(file:UploadFile=File(...)):
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in ALLOWED_MEDIA: raise HTTPException(415,'Поддерживаются аудио и видео MP3/WAV/M4A/MP4/MOV/WEBM и др.')
    content=await file.read(100*1024*1024+1)
    if len(content)>100*1024*1024: raise HTTPException(413,'Максимальный файл — 100 МБ')
    mid=uuid.uuid4().hex
    path=MEDIA/(mid+suffix)
    path.write_bytes(content)
    return {'id':mid,'filename':file.filename,'url':f'/api/media/{path.name}','bytes':len(content)}

@app.get('/api/media/{filename}')
def serve_media(filename:str):
    path=MEDIA/Path(filename).name
    if not path.is_file() or filename!=path.name: raise HTTPException(404,'Файл не найден')
    return FileResponse(path)

class AudioCut(BaseModel):
    filename:str
    start:float=Field(ge=0)
    end:float=Field(gt=0)
    denoise:bool=False
    normalize:bool=True
    consent_confirmed:bool=False

@app.post('/api/audio/cut')
def audio_cut(data:AudioCut):
    # Consent is mandatory for preparing a vocal likeness reference export.
    if not data.consent_confirmed: raise HTTPException(400,'Подтверди право использовать голос в этом материале')
    path=MEDIA/Path(data.filename).name
    if data.filename!=path.name or not path.exists(): raise HTTPException(404,'Исходник не найден')
    if data.end<=data.start or data.end-data.start>180: raise HTTPException(400,'Выбери интервал 0–180 секунд')
    output=MEDIA/(uuid.uuid4().hex+'.wav')
    filters=['highpass=f=80']
    if data.denoise: filters.append('afftdn=nf=-25')
    if data.normalize: filters.append('loudnorm=I=-16:TP=-1.5:LRA=11')
    cmd(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(data.start),'-i',str(path),'-t',str(data.end-data.start),'-vn','-ac','1','-ar','44100','-af',','.join(filters),str(output)])
    return {'url':f'/api/media/{output.name}','filename':output.name,'duration':round(data.end-data.start,2),'settings':{'mono':True,'sample_rate':44100,'denoise':data.denoise,'normalize':data.normalize}}

@app.get('/api/audio/analyze/{filename}')
def audio_analyze(filename:str):
    path=MEDIA/Path(filename).name
    if filename!=path.name or not path.exists(): raise HTTPException(404,'Файл не найден')
    probe=cmd(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)])
    duration=float(probe.stdout.strip() or 0)
    if duration>3600:raise HTTPException(422,'Для анализа выбери материал короче 60 минут')
    # Silence boundaries are candidate editing points; do not mislabel as verified best voice takes.
    scan=cmd(['ffmpeg','-hide_banner','-i',str(path),'-af','silencedetect=noise=-35dB:d=0.35','-f','null','-'])
    marks=[0.0]+[float(x) for x in re.findall(r'silence_(?:start|end):\s*([\d.]+)',scan.stderr)]+[duration]
    marks=sorted(set(min(duration,max(0,x)) for x in marks))
    candidates=[{'start':round(a,2),'end':round(b,2),'duration':round(b-a,2)} for a,b in zip(marks,marks[1:]) if 2<=b-a<=35]
    return {'duration':round(duration,2),'suggested_segments':candidates[:25],'method':'Паузы и длительность; содержимое речи автоматически не оценивается'}


# Agent prototype: staged orchestration; LLM calls only, no autonomous paid image/video tasks.
AGENT_ROLES = {
 'director': 'You are AI Director for cinematic AI video. Break the brief into a concise shot plan, physical blocking, and shot objectives. Never silently change canonical character identity or project world.',
 'continuity': 'You are Continuity Agent. Identify risk of character identity drift, wrong wardrobe, wrong location, and style conflicts. Treat approved references as authoritative; failed examples are warnings, not positive references.',
 'prompt': 'You are Prompt Agent. Write distinct production-grade image and video prompts respecting model capabilities. Do not invent API params. Each image model may need its own character profile; distinguish still composition from motion.',
}

class AgentRunRequest(BaseModel):
    project_id: str|None = None
    brief: str = Field(min_length=3,max_length=12000)
    provider: str = 'openai'
    model: str = 'gpt-4.1-mini'
    character: dict[str,Any] = Field(default_factory=dict)
    style: dict[str,Any] = Field(default_factory=dict)
    target_models: list[str] = Field(default_factory=lambda:['seedream-5-pro','seedance-2.5'])

@app.get('/api/agents/config')
def agent_config():
    return {'roles':list(AGENT_ROLES),'providers':['openai','piapi'],'note':'Only LLM planning is executed. Generation requires separate approval. No API keys are saved.'}

async def agent_completion(provider:str,model:str,key:str,system:str,prompt:str):
    if provider=='openai':
        if not model.startswith(('gpt-','o')): raise HTTPException(400,'Unknown OpenAI model')
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                response=await client.post('https://api.openai.com/v1/responses',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},json={'model':model,'instructions':system,'input':prompt,'max_output_tokens':1400})
        except httpx.RequestError as e: raise HTTPException(502,'OpenAI connection failed: '+type(e).__name__)
        if response.is_error: raise HTTPException(response.status_code,{'provider':'openai','error':response.text[:1200]})
        value=response.json()
        fragments=[c.get('text','') for item in value.get('output',[]) if item.get('type')=='message' for c in item.get('content',[]) if c.get('type')=='output_text']
        return '\n'.join(fragments).strip(),value.get('usage',{})
    if provider=='piapi':
        if model not in ALLOWED_CHAT: raise HTTPException(400,'Unknown PiAPI LLM model')
        value=await request_piapi('POST','/v1/chat/completions',key,{'model':model,'messages':[{'role':'system','content':system},{'role':'user','content':prompt}]})
        return value.get('choices',[{}])[0].get('message',{}).get('content',''),value.get('usage',{})
    raise HTTPException(400,'Unknown provider')

@app.post('/api/agents/run')
async def run_agents(body:AgentRunRequest,x_api_key:str|None=Header(default=None)):
    key=get_key(x_api_key) if body.provider=='piapi' else provider_key(body.provider,x_api_key)
    if not key or not key.isascii() or any(x.isspace() for x in key): raise HTTPException(400,'Enter a valid API key (ASCII, no spaces)')
    if len(body.target_models)>8:raise HTTPException(400,'Limit 8 target models')
    for target in body.target_models:
        if target not in MODEL_SPECS:raise HTTPException(400,'No verified API schema for '+target)
    context={'brief':body.brief,'character_identity':body.character.get('identity',{}),'model_profiles':body.character.get('profiles',{}),'project_style_bible':body.style,'target_models':{m:MODEL_SPECS[m] for m in body.target_models}}
    output={}
    for role,instructions in AGENT_ROLES.items():
        previous=json.dumps(output,ensure_ascii=False)
        prompt=json.dumps(context,ensure_ascii=False)+'\nPREVIOUS SPECIALISTS:\n'+previous
        if role=='prompt': instructions+=' Respond with labelled sections for each target model, then a short list of required references and parameters.'
        content,usage=await agent_completion(body.provider,body.model,key,instructions,prompt)
        output[role]={'content':content,'usage':usage}
    run_id=uuid.uuid4().hex
    record={'id':run_id,'created_at':now(),'provider':body.provider,'model':body.model,'brief':body.brief,'target_models':body.target_models,'output':output,'status':'awaiting_user_approval','generation_started':False}
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS agent_runs(id TEXT PRIMARY KEY,project_id TEXT,created_at TEXT,data TEXT)')
        db.execute('INSERT INTO agent_runs VALUES(?,?,?,?)',(run_id,body.project_id,record['created_at'],json.dumps(record,ensure_ascii=False)))
    return record

@app.get('/api/agents/runs')
def agent_runs(project_id:str|None=None):
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS agent_runs(id TEXT PRIMARY KEY,project_id TEXT,created_at TEXT,data TEXT)')
        rows=db.execute('SELECT data FROM agent_runs WHERE project_id=? ORDER BY created_at DESC LIMIT 20',(project_id,)).fetchall() if project_id else db.execute('SELECT data FROM agent_runs ORDER BY created_at DESC LIMIT 20').fetchall()
        return [json.loads(row['data']) for row in rows]


# Generated originals are stored locally with their request and model provenance.
LIBRARY_ROOT=(DATA or ROOT)/'library'

def library_record(row):
    metadata=json.loads(row['metadata'])
    return {**dict(row),'metadata':metadata,'url':f'/api/library/{row["id"]}/file','provider_reference_url':reference_upload.reference_url(sys.modules[__name__],row),'thumbnail_url':None if metadata.get('kind') in {'video','audio'} else f'/api/library/{row["id"]}/thumbnail'}

@app.get('/api/library')
def list_library(project_id:str):
    project(project_id)
    with connect() as db:
        rows=db.execute('''SELECT DISTINCT a.* FROM library_assets a WHERE a.project_id=? OR a.id IN (
            SELECT f.asset_id FROM production_files f JOIN production_nodes n ON n.id=f.node_id JOIN production_links l ON l.production_id=f.production_id
            WHERE l.project_id=? AND n.kind IN ('character','location') AND f.asset_id IS NOT NULL) ORDER BY a.created_at DESC''',(project_id,project_id)).fetchall()
    return [library_record(row) for row in rows]

@app.get('/api/library/{asset_id}/file')
def library_file(asset_id:str):
    checked_id(asset_id)
    with connect() as db: row=db.execute('SELECT * FROM library_assets WHERE id=?',(asset_id,)).fetchone()
    if not row: raise HTTPException(404,'Ассет не найден')
    path=LIBRARY_ROOT/row['filename']
    if not path.is_file(): raise HTTPException(404,'Файл ассета отсутствует')
    return FileResponse(path)

@app.get('/api/library/{asset_id}/thumbnail')
def library_thumbnail(asset_id:str):
    from PIL import Image,ImageOps
    checked_id(asset_id)
    with connect() as db:row=db.execute('SELECT * FROM library_assets WHERE id=?',(asset_id,)).fetchone()
    if not row or json.loads(row['metadata']).get('kind') in {'video','audio'}:raise HTTPException(404,'Миниатюра изображения отсутствует')
    source=(LIBRARY_ROOT/row['filename']).resolve()
    if not source.is_relative_to(LIBRARY_ROOT.resolve()) or not source.is_file():raise HTTPException(404,'Оригинал отсутствует')
    directory=LIBRARY_ROOT/'.thumbnails';directory.mkdir(parents=True,exist_ok=True)
    thumbnail=directory/(asset_id+'.webp')
    if not thumbnail.is_file():
        with Image.open(source) as original:
            image=ImageOps.exif_transpose(original).convert('RGB');image.thumbnail((512,512));image.save(thumbnail,'WEBP',quality=82)
    return FileResponse(thumbnail,media_type='image/webp',headers={'Cache-Control':'private, max-age=86400'})

OUTPUT_LOCKS={}

@app.post('/api/jobs/{job_id}/outputs/{output_index}/save')
@app.post('/api/jobs/{job_id}/images/{output_index}/save')
async def save_job_image(job_id:str,output_index:int):
    async with OUTPUT_LOCKS.setdefault((job_id,output_index),asyncio.Lock()):
        return await _save_job_output(job_id,output_index)

async def _save_job_output(job_id:str,output_index:int):
    with connect() as db:
        row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        existing=db.execute('SELECT * FROM library_assets WHERE job_id=? AND output_index=?',(job_id,output_index)).fetchone()
    if not row or row['kind'] not in {'image','video'}: raise HTTPException(404,'Задание изображения не найдено')
    if not row['project_id']: raise HTTPException(400,'Задание не связано с сохранённым проектом')
    project(row['project_id'])
    if existing and (LIBRARY_ROOT/existing['filename']).is_file(): return library_record(existing)
    if row['status']!='completed': raise HTTPException(409,'Изображение ещё не готово')
    urls=output_urls(json.loads(row['response']),row['kind'])
    if not 0<=output_index<len(urls): raise HTTPException(400,'Нет такого результата в задании')
    is_video=row['kind']=='video'
    content=await (download_video(urls[output_index]) if is_video else download_image(urls[output_index]))
    if is_video:
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            probe_file=Path(temporary)/'result.mp4';probe_file.write_bytes(content)
            probe=json.loads(cmd(['ffprobe','-v','error','-show_entries','stream=codec_type,width,height:format=duration,format_name','-of','json',str(probe_file)]).stdout)
            stream=next((v for v in probe.get('streams',[]) if v.get('codec_type')=='video'),None)
            if not stream or not any(v in probe.get('format',{}).get('format_name','').split(',') for v in ('mp4','mov')): raise HTTPException(422,'Результат не является MP4/MOV с видеодорожкой')
            image={'format':'MP4','width':stream['width'],'height':stream['height'],'duration':float(probe.get('format',{}).get('duration',0))}
    else: image=inspect_image(content)
    aid=existing['id'] if existing else uuid.uuid4().hex
    ext={'PNG':'.png','JPEG':'.jpg','WEBP':'.webp','MP4':'.mp4'}[image['format']]
    filename=existing['filename'] if existing else aid+ext
    LIBRARY_ROOT.mkdir(parents=True,exist_ok=True)
    path=LIBRARY_ROOT/filename
    path.write_bytes(content)
    metadata={'request':json.loads(row['request']),'provider':row['provider'],'kind':row['kind'],**image}
    try:
        with connect() as db:
            db.execute('INSERT INTO library_assets VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET metadata=excluded.metadata',(aid,job_id,row['project_id'],output_index,filename,urls[output_index],json.dumps(metadata,ensure_ascii=False),now()))
    except sqlite3.IntegrityError:
        path.unlink(missing_ok=True)
        with connect() as db: result=db.execute('SELECT * FROM library_assets WHERE job_id=? AND output_index=?',(job_id,output_index)).fetchone()
        return library_record(result)
    with connect() as db: result=db.execute('SELECT * FROM library_assets WHERE id=?',(aid,)).fetchone()
    production_folders.sync_asset(sys.modules[__name__],aid)
    return library_record(result)


from backend.native_chat import register as register_native_chat
import sys
register_native_chat(app,sys.modules[__name__])
from backend.economics import register as register_economics
register_economics(app,sys.modules[__name__])
from backend.refinement import register as register_refinement
register_refinement(app,sys.modules[__name__])
from backend.external_generation import register as register_external
register_external(app,sys.modules[__name__])
from backend.activity import register as register_activity
register_activity(app,sys.modules[__name__])
from backend.send_to_reference import register as register_send_to_reference
register_send_to_reference(app,sys.modules[__name__])
from backend.character_versions import register as register_character_versions
register_character_versions(app,sys.modules[__name__])
from backend import security
security.register(app,sys.modules[__name__])
from backend.job_recovery import register as register_job_recovery
register_job_recovery(app,sys.modules[__name__])
from backend.job_delivery import register as register_job_delivery
register_job_delivery(app,sys.modules[__name__])
from backend import reference_upload
reference_upload.register(app,sys.modules[__name__])
from backend import production_folders
production_folders.register(app,sys.modules[__name__])
from backend import storyboard
storyboard.register(app,sys.modules[__name__])
from backend import production_entities
production_entities.register(app,sys.modules[__name__])
from backend import series_economics
series_economics.register(app,sys.modules[__name__])
from backend import character_voice
character_voice.register(app,sys.modules[__name__])
camera_movements.register(app)
frame_composition.register(app)
from backend.temp_cleanup import register as register_temp_cleanup
register_temp_cleanup(app,sys.modules[__name__])
from backend import remote_access
remote_access.register(app,sys.modules[__name__])
remote_access.mount_frontend(app,ROOT.parent)
