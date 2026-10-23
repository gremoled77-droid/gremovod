"""Character voice cards and explicitly approved, budgeted TTS requests."""
import json
import re
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field
from backend import production_folders as folders, security

MODELS={'elevenlabs':{'eleven_multilingual_v2':0.00008,'eleven_v3':0.00008,'eleven_v4':0.00008},'fish':{'s2.1-pro':0.000015,'s2.1-pro-free':0}}
SOURCES={'elevenlabs':'https://elevenlabs.io/pricing/api','fish':'https://docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits'}

class Voice(BaseModel):
    provider:str='elevenlabs'
    name:str=Field(default='',max_length=150)
    voice_id:str=Field(default='',max_length=100)
    url:str=Field(default='',max_length=1000)
    model:str='eleven_multilingual_v2'
    cost_multiplier:float=Field(default=1,ge=1,le=20,allow_inf_nan=False)

class Phrase(BaseModel):
    text:str=Field(min_length=1,max_length=3000)
    project_id:str
    voice_library_id:str=Field(default='',max_length=100)

class Generate(Phrase):
    request_id:str=Field(pattern=r'^[a-zA-Z0-9_-]{16,100}$')
    quote_token:str
    max_cost_usd:float=Field(ge=0,le=20,allow_inf_nan=False)
    approved:bool=False

def target(studio,pid,nid):
    info=folders.node(studio,pid,nid)
    if info['kind']!='character':raise HTTPException(400,'Голос закрепляется за персонажем')
    return info

def read_voice(studio,nid):
    with studio.connect() as db:row=db.execute('SELECT profile FROM character_voices WHERE node_id=?',(nid,)).fetchone()
    return json.loads(row['profile']) if row else Voice().model_dump()

def document(studio,info):
    voice=read_voice(studio,info['id'])
    with studio.connect() as db:files=[dict(r) for r in db.execute("SELECT * FROM production_files WHERE node_id=? AND kind='audio'",(info['id'],))]
    base=Path(info['relative_dir'])
    folders.write_text(studio,str(base/'04_Голос'/'ГОЛОС.json'),json.dumps({**voice,'audio_files':[f['relative_path'] for f in files]},ensure_ascii=False,indent=2))
    text=f'# Голос: {info["title"]}\n\nСервис: {voice["provider"]}\nНазвание: {voice["name"] or "не выбрано"}\nVoice ID: {voice["voice_id"] or "не указан"}\nСсылка: {voice["url"] or "не указана"}\nМодель: {voice["model"]}\n\n'
    text+='Аудиофайлы:\n'+('\n'.join('- '+f['filename'] for f in files) or 'Аудиопример ещё не прикреплён.')+'\n'
    folders.write_text(studio,str(base/'04_Голос'/'ГОЛОС.md'),text)
    common=folders.production(studio,info['production_id']);state=studio.project(common['source_project_id'])['state']
    character=next((c for c in state.get('characters',[]) if c['id']==info['character_id']),{})
    card=f'# Референс-карта: {info["title"]}\n\n'+info['notes']+'\n\n'
    card+='## Внешность и ограничения\n\n'+json.dumps(character.get('identity',{}),ensure_ascii=False,indent=2)+'\n\n'
    card+='Основной образ: `01_Основной_образ/`\nРеференсы: `02_Референсы/`\nПредыдущие версии: `03_Архив/`\n\n'+text
    with studio.connect() as db:
        primary=db.execute("SELECT relative_path FROM production_files WHERE node_id=? AND asset_id=?",(info['id'],character.get('working_asset_id',''))).fetchone()
    if primary:card+='\n## Утверждённый образ\n\n![Утверждённый образ]('+Path(primary['relative_path']).relative_to(base).as_posix()+')\n'
    folders.write_text(studio,str(base/'РЕФЕРЕНС_КАРТА.md'),card)

async def request_audio(voice,text,key):
    if voice['provider']=='elevenlabs':
        url='https://api.elevenlabs.io/v1/text-to-speech/'+voice['voice_id']
        headers={'xi-api-key':key};params={'output_format':'mp3_44100_128'}
        payload={'text':text,'model_id':voice['model']}
    else:
        url='https://api.fish.audio/v1/tts';params={}
        headers={'Authorization':'Bearer '+key,'model':voice['model']}
        payload={'text':text,'reference_id':voice['voice_id'],'format':'mp3','sample_rate':44100,'mp3_bitrate':128,'latency':'normal'}
    try:
        async with httpx.AsyncClient(timeout=150,follow_redirects=False) as client:
            async with client.stream('POST',url,headers=headers,params=params,json=payload) as response:
                if response.status_code!=200:raise HTTPException(502 if response.status_code>=500 else 400,f'Сервис озвучки отклонил запрос (HTTP {response.status_code}). Проверь доступ к голосу и тариф.')
                content=bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content)>30*1024*1024:raise HTTPException(502,'Ответ озвучки превышает 30 МБ')
                return bytes(content)
    except httpx.RequestError:raise HTTPException(502,'Ответ озвучки не получен. Проверь историю сервиса перед новым запуском.')

def inspect_audio(path):
    try:
        result=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type:format=duration','-of','json',str(path)],capture_output=True,text=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        info=json.loads(result.stdout)
        if result.returncode or not any(s.get('codec_type')=='audio' for s in info['streams']) or float(info['format']['duration'])<=0:raise ValueError()
        return float(info['format']['duration'])
    except (ValueError,KeyError,OSError,subprocess.TimeoutExpired):raise HTTPException(502,'Сервис не вернул корректный аудиофайл')

def register(app,studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS character_voices(node_id TEXT PRIMARY KEY,profile TEXT NOT NULL,updated_at TEXT NOT NULL)')

    prefix='/api/productions/{pid}/nodes/{nid}/voice'
    @app.get(prefix)
    def get_voice(pid:str,nid:str):
        target(studio,pid,nid)
        return read_voice(studio,nid)

    @app.put(prefix)
    def save_voice(pid:str,nid:str,body:Voice):
        info=target(studio,pid,nid)
        if body.provider not in MODELS or body.model not in MODELS[body.provider]:raise HTTPException(400,'Выбери поддерживаемую модель озвучки')
        if body.voice_id and not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',body.voice_id):raise HTTPException(400,'Некорректный Voice ID')
        if body.voice_id and not body.name.strip():raise HTTPException(400,'Укажи название голоса')
        if body.url:
            url=urlparse(body.url);domain=url.hostname or ''
            allowed='elevenlabs.io' if body.provider=='elevenlabs' else 'fish.audio'
            if url.scheme!='https' or (domain!=allowed and not domain.endswith('.'+allowed)) or url.username or url.password:raise HTTPException(400,'Нужна HTTPS-ссылка на страницу выбранного сервиса')
        profile=body.model_dump()
        with studio.connect() as db:db.execute('INSERT INTO character_voices VALUES(?,?,?) ON CONFLICT(node_id) DO UPDATE SET profile=excluded.profile,updated_at=excluded.updated_at',(nid,json.dumps(profile,ensure_ascii=False),studio.now()))
        document(studio,info)
        return profile

    def estimate(pid,nid,body):
        target(studio,pid,nid);membership=folders.link(studio,body.project_id)
        if not membership or membership['production_id']!=pid:raise HTTPException(400,'Выбери кадр этого общего проекта для учёта расходов')
        voice=read_voice(studio,nid)
        if body.voice_library_id:
            with studio.connect() as db:
                row=db.execute('SELECT v.* FROM voice_library v JOIN hero_voices h ON h.voice_lib_id=v.id WHERE v.id=? AND v.production_id=? AND v.archived=0 AND h.node_id=?',(body.voice_library_id,pid,nid)).fetchone()
            if not row:raise HTTPException(400,'Этот голос не привязан к герою')
            voice={'provider':row['provider'],'name':row['name'],'voice_id':row['voice_id'],'url':row['url'],'model':row['model'],'cost_multiplier':voice.get('cost_multiplier',1)}
        if not voice['voice_id'] or not voice['name']:raise HTTPException(400,'Сначала сохрани название голоса и Voice ID')
        if not body.text.strip():raise HTTPException(400,'Напиши фразу')
        units=len(body.text.encode('utf-8')) if voice['provider']=='fish' else len(body.text)
        cost=round(units*MODELS[voice['provider']][voice['model']]*voice['cost_multiplier'],8)
        payload={'production_id':pid,'node_id':nid,'voice':voice,'text':body.text}
        return voice,cost,payload

    @app.post(prefix+'/estimate')
    def quote(pid:str,nid:str,body:Phrase):
        voice,cost,payload=estimate(pid,nid,body)
        return {'estimated_usd':cost,'quote_token':security.quote(body.project_id,payload,cost),'source':SOURCES[voice['provider']],'note':'Оценка по базовому API-тарифу от 15.10.2026. Множитель задаётся в карточке голоса; фактическое списание зависит от тарифа и выбранного голоса.'}

    @app.post(prefix+'/generate')
    async def generate(pid:str,nid:str,body:Generate):
        voice,cost,payload=estimate(pid,nid,body)
        stored=json.dumps(payload,ensure_ascii=False)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM jobs WHERE id=?',(body.request_id,)).fetchone()
            if old:
                if old['project_id']!=body.project_id or old['request']!=stored:raise HTTPException(409,'ID запроса уже занят другой фразой')
                return {'job_id':old['id'],'status':old['status'],'duplicate':True}
            if not body.approved or body.max_cost_usd<cost:raise HTTPException(400,'Подтверди оценку стоимости озвучки')
            security.verify_quote(body.quote_token,body.project_id,payload,cost)
            key=studio.provider_key(voice['provider']);security.check_budget(db,body.project_id,cost)
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',(body.request_id,body.project_id,'audio',voice['provider'],None,'submitting',stored,'{}',studio.now()))
            db.execute('INSERT INTO generation_approvals VALUES(?,?,?,?,?)',(body.request_id,cost,body.max_cost_usd,studio.now(),'documentation_estimate'))
        try:
            content=await request_audio(voice,body.text,key)
            if not content:raise HTTPException(502,'Пустой аудиофайл')
            fid=uuid.uuid4().hex;filename=fid+'.mp3';studio.LIBRARY_ROOT.mkdir(parents=True,exist_ok=True)
            path=studio.LIBRARY_ROOT/filename;path.write_bytes(content);duration=inspect_audio(path)
            metadata={'kind':'audio','provider':voice['provider'],'model':voice['model'],'voice':voice,'character_id':target(studio,pid,nid)['character_id'],'text':body.text,'duration_seconds':duration,'request':{'payload':payload}}
            with studio.connect() as db:
                db.execute('INSERT INTO library_assets VALUES(?,?,?,?,?,?,?,?)',(fid,body.request_id,body.project_id,0,filename,'',json.dumps(metadata,ensure_ascii=False),studio.now()))
                db.execute("UPDATE jobs SET status='completed',response=? WHERE id=?",(json.dumps({'asset_id':fid}),body.request_id))
            folders.copy_asset(studio,pid,nid,fid,'04_Голос');folders.sync_asset(studio,fid);document(studio,target(studio,pid,nid))
            return {'job_id':body.request_id,'status':'completed','asset_id':fid}
        except Exception as exc:
            status='failed' if isinstance(exc,HTTPException) and exc.status_code<500 else 'submission_unknown'
            with studio.connect() as db:db.execute('UPDATE jobs SET status=? WHERE id=?',(status,body.request_id))
            if isinstance(exc,HTTPException):raise exc
            raise HTTPException(502,'Не удалось сохранить результат озвучки. Проверь очередь и историю сервиса перед новым запуском.')
