"""Human-readable production folders, shared references and per-frame studio projects."""
import json
import re
import shutil
import sys
import uuid
from pathlib import Path

from fastapi import File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT_GROUPS={'character':'01_Персонажи','location':'02_Локации','series':'03_Серии'}
GROUPS={
    'character':['01_Основной_образ','02_Референсы','03_Архив','04_Голос'],
    'location':['01_Референсы','02_Изображения','03_Видео'],
    'series':['01_Сценарий','02_Эпизоды','03_Монтаж','04_Экспорт'],
    'episode':['01_Сценарий','02_Раскадровка','03_Кадры'],
    'frame':['01_Исходники','02_Изображения','03_Видео','04_Звук','05_Промпты','06_Выбранное'],
}
NOTE_FILES={'character':'ПЕРСОНАЖ.md','location':'ЛОКАЦИЯ.md','series':'01_Сценарий/СЮЖЕТ.md','episode':'01_Сценарий/СЦЕНА.md','frame':'КАДР.md'}
EXTENSIONS={'.png','.jpg','.jpeg','.webp','.mp4','.mov','.webm','.mp3','.wav','.m4a','.txt','.md','.json','.pdf','.srt'}


def safe_name(value):
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',value).strip(' .')[:75]
    if not name or name in {'.','..'} or re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])',name.split('.')[0]):
        raise HTTPException(400,'Укажи допустимое название папки')
    return name


def checked_path(studio,relative):
    root=studio.PRODUCTIONS_ROOT.resolve()
    path=(root/relative).resolve()
    if not path.is_relative_to(root):raise HTTPException(400,'Путь выходит за папку проектов')
    # Keep stored relative paths and existing folders intact. Win32's extended
    # syntax allows long scene/frame paths without a machine-wide registry edit.
    if sys.platform=='win32':
        value=str(path)
        if not value.startswith('\\\\?\\'):
            path=Path('\\\\?\\UNC\\'+value[2:] if value.startswith('\\\\') else '\\\\?\\'+value)
    return path


def write_text(studio,relative,text):
    path=checked_path(studio,relative);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(text,encoding='utf-8');temporary.replace(path)


def production(studio,pid):
    with studio.connect() as db:row=db.execute('SELECT * FROM productions WHERE id=?',(pid,)).fetchone()
    if not row:raise HTTPException(404,'Общий проект не найден')
    return dict(row)


def node(studio,pid,nid):
    with studio.connect() as db:row=db.execute('SELECT * FROM production_nodes WHERE id=? AND production_id=?',(nid,pid)).fetchone()
    if not row:raise HTTPException(404,'Папка проекта не найдена')
    return dict(row)


def link(studio,project_id):
    with studio.connect() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='production_links'").fetchone():return None
        row=db.execute('SELECT l.*,p.source_project_id,p.folder,p.title FROM production_links l JOIN productions p ON p.id=l.production_id WHERE l.project_id=?',(project_id,)).fetchone()
    return dict(row) if row else None


def shared_characters(studio,project_id,state):
    membership=link(studio,project_id)
    if not membership:return state
    with studio.connect() as db:
        source=db.execute('SELECT state FROM projects WHERE id=?',(membership['source_project_id'],)).fetchone()
        ids={r['character_id'] for r in db.execute("SELECT character_id FROM production_nodes WHERE production_id=? AND kind='character'",(membership['production_id'],))}
    if not source:return state
    common=[c for c in json.loads(source['state']).get('characters',[]) if c['id'] in ids]
    own=[c for c in state.get('characters',[]) if c['id'] not in ids]
    return {**state,'characters':[*common,*own]}


def character_owner(studio,project_id,character_id):
    membership=link(studio,project_id)
    if membership:
        with studio.connect() as db:
            found=db.execute("SELECT 1 FROM production_nodes WHERE production_id=? AND kind='character' AND character_id=?",(membership['production_id'],character_id)).fetchone()
        if found:return membership['source_project_id']
    return project_id


def accessible_asset(studio,db,asset_id,project_id):
    return db.execute('''SELECT a.* FROM library_assets a WHERE a.id=? AND (a.project_id=? OR EXISTS(
        SELECT 1 FROM production_files f JOIN production_nodes n ON n.id=f.node_id JOIN production_links l ON l.production_id=f.production_id
        WHERE f.asset_id=a.id AND l.project_id=? AND n.kind IN ('character','location')))''',(asset_id,project_id,project_id)).fetchone()


def copy_asset(studio,pid,nid,asset_id,category=None):
    target=node(studio,pid,nid)
    with studio.connect() as db:
        asset=db.execute('SELECT * FROM library_assets WHERE id=?',(asset_id,)).fetchone()
        allowed=db.execute('SELECT 1 FROM production_links WHERE production_id=? AND project_id=?',(pid,asset['project_id'] if asset else '')).fetchone()
    if not asset or not allowed:raise HTTPException(404,'Файл не принадлежит этому общему проекту')
    metadata=json.loads(asset['metadata']);kind=metadata.get('kind','image')
    if category is None:
        category=({'character':'02_Референсы','location':'03_Видео' if kind=='video' else '01_Референсы',
                   'frame':'04_Звук' if kind=='audio' else ('03_Видео' if kind=='video' else ('01_Исходники' if metadata.get('provider')=='local_import' else '02_Изображения'))}).get(target['kind'])
    if category not in GROUPS[target['kind']]:raise HTTPException(400,'Выбери раздел внутри папки')
    source=(studio.LIBRARY_ROOT/asset['filename']).resolve()
    if not source.is_relative_to(studio.LIBRARY_ROOT.resolve()) or not source.is_file():raise HTTPException(404,'Оригинал отсутствует')
    relative=str(Path(target['relative_dir'])/category/asset['filename'])
    path=checked_path(studio,relative);path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():shutil.copy2(source,path)
    fid=uuid.uuid5(uuid.NAMESPACE_URL,f'{nid}/{asset_id}/{category}').hex
    with studio.connect() as db:
        db.execute('INSERT OR IGNORE INTO production_files(id,production_id,node_id,asset_id,filename,relative_path,kind,created_at) VALUES(?,?,?,?,?,?,?,?)',
                   (fid,pid,nid,asset_id,asset['filename'],relative,kind,studio.now()))
    write_text(studio,relative+'.json',json.dumps({'asset_id':asset_id,'source_project_id':asset['project_id'],'source_job_id':asset['job_id'],'metadata':metadata},ensure_ascii=False,indent=2))
    return fid


def sync_asset(studio,asset_id):
    with studio.connect() as db:asset=db.execute('SELECT project_id FROM library_assets WHERE id=?',(asset_id,)).fetchone()
    if not asset:return
    membership=link(studio,asset['project_id'])
    if membership and membership['node_id']:
        copy_asset(studio,membership['production_id'],membership['node_id'],asset_id)


def sync_character(studio,project_id,character_id):
    owner=character_owner(studio,project_id,character_id)
    membership=link(studio,owner)
    if not membership:return
    with studio.connect() as db:
        target=db.execute("SELECT * FROM production_nodes WHERE production_id=? AND character_id=? AND kind='character'",(membership['production_id'],character_id)).fetchone()
        source=db.execute('SELECT state FROM projects WHERE id=?',(owner,)).fetchone()
        assets=db.execute('SELECT * FROM library_assets WHERE project_id IN (SELECT project_id FROM production_links WHERE production_id=?)',(membership['production_id'],)).fetchall()
        refs=db.execute('SELECT * FROM character_assets WHERE project_id=? AND character_id=?',(owner,character_id)).fetchall()
    if not target or not source:return
    character=next((c for c in json.loads(source['state']).get('characters',[]) if c['id']==character_id),None)
    if not character:return
    for asset in assets:
        meta=json.loads(asset['metadata'])
        if meta.get('character_id')!=character_id:continue
        if meta.get('kind')=='audio':
            copy_asset(studio,membership['production_id'],target['id'],asset['id'],'04_Голос')
            continue
        category='01_Основной_образ' if asset['id']==character.get('working_asset_id') else ('02_Референсы' if meta.get('character_status')=='reference' else '03_Архив')
        copy_asset(studio,membership['production_id'],target['id'],asset['id'],category)
    # Old primary files become archive entries; originals stay in the canonical library.
    with studio.connect() as db:
        old=db.execute("SELECT * FROM production_files WHERE node_id=? AND asset_id IS NOT NULL",(target['id'],)).fetchall()
        for item in old:
            if '01_Основной_образ' in Path(item['relative_path']).parts and item['asset_id']!=character.get('working_asset_id'):
                previous=checked_path(studio,item['relative_path'])
                if previous.is_file():previous.unlink()
                sidecar=checked_path(studio,item['relative_path']+'.json');sidecar.unlink(missing_ok=True)
                db.execute('DELETE FROM production_files WHERE id=?',(item['id'],))
    for ref in refs:
        if ref['category'] not in {'real_references','model_references'}:continue
        source_path=(studio.char_directory(owner,character_id,ref['category'],ref['model_id'] or '')/ref['filename']).resolve()
        if not source_path.is_relative_to(studio.CHAR_ROOT.resolve()) or not source_path.is_file():continue
        relative=str(Path(target['relative_dir'])/'02_Референсы'/ref['filename'])
        destination=checked_path(studio,relative);destination.parent.mkdir(parents=True,exist_ok=True)
        if not destination.exists():shutil.copy2(source_path,destination)
        fid=uuid.uuid5(uuid.NAMESPACE_URL,f'{target["id"]}/vault/{ref["id"]}').hex
        with studio.connect() as db:
            db.execute('INSERT OR IGNORE INTO production_files VALUES(?,?,?,?,?,?,?,?)',(fid,membership['production_id'],target['id'],None,ref['original_name'],relative,'image',studio.now()))
    write_text(studio,str(Path(target['relative_dir'])/'ПРОФИЛЬ.json'),json.dumps(character,ensure_ascii=False,indent=2))
    from backend import character_voice
    character_voice.document(studio,dict(target))


def sync_project(studio,project_id):
    membership=link(studio,project_id)
    if not membership:return
    state=studio.project(project_id)['state']
    if membership['node_id']:
        target=node(studio,membership['production_id'],membership['node_id'])
        with studio.connect() as db:assets=db.execute('SELECT id FROM library_assets WHERE project_id=?',(project_id,)).fetchall()
        for asset in assets:sync_asset(studio,asset['id'])
        write_text(studio,str(Path(target['relative_dir'])/'05_Промпты'/'ЗАДАНИЕ_СТУДИИ.json'),json.dumps({'project_id':project_id,'brief':state.get('brief'),'prompts':state.get('prompts',{}),'scene':state.get('scene',{}),'parameters':state.get('parameters',{}),'camera':state.get('camera'),'composition':state.get('composition'),'cameraPromptBasis':state.get('cameraPromptBasis',{}),'compositionPromptBasis':state.get('compositionPromptBasis',{})},ensure_ascii=False,indent=2))
        with studio.connect() as db:history=[dict(r) for r in db.execute('SELECT id,target,prompt,provider,model,created_at FROM prompt_versions WHERE project_id=? ORDER BY created_at',(project_id,))]
        write_text(studio,str(Path(target['relative_dir'])/'05_Промпты'/'ИСТОРИЯ_ПРОМПТОВ.json'),json.dumps(history,ensure_ascii=False,indent=2))
    for character in state.get('characters',[]):sync_character(studio,project_id,character['id'])


def create_node(studio,pid,body):
    common=production(studio,pid)
    parent=node(studio,pid,body.parent_id) if body.parent_id else None
    valid=(body.kind in ROOT_GROUPS and parent is None) or (body.kind=='episode' and parent and parent['kind']=='series') or (body.kind=='frame' and parent and parent['kind']=='episode')
    if not valid:raise HTTPException(400,'Порядок папок: общий проект → серия → эпизод/сцена → кадр')
    title=safe_name(body.title);guest=safe_name(body.guest) if body.guest.strip() else ''
    if guest and body.kind!='series':raise HTTPException(400,'Гость указывается в папке серии')
    if body.kind=='character' and body.character_id:
        if not any(c['id']==body.character_id for c in studio.project(common['source_project_id'])['state'].get('characters',[])):
            raise HTTPException(400,'Персонаж отсутствует в библиотеке общего проекта')
    nid=uuid.uuid4().hex
    with studio.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        number=body.number
        if number is None:number=db.execute('SELECT COALESCE(MAX(number),0)+1 FROM production_nodes WHERE production_id=? AND parent_id IS ? AND kind=?',(pid,body.parent_id,body.kind)).fetchone()[0]
        if db.execute('SELECT 1 FROM production_nodes WHERE production_id=? AND parent_id IS ? AND kind=? AND (number=? OR title=?)',(pid,body.parent_id,body.kind,number,body.title.strip())).fetchone():raise HTTPException(409,'Папка с таким номером или названием уже есть')
        base=Path(common['folder'])/ROOT_GROUPS[body.kind] if parent is None else Path(parent['relative_dir'])/('02_Эпизоды' if body.kind=='episode' else '03_Кадры')
        name=title if body.kind in {'character','location'} else f'{number:03d}_{title}'+(' — '+guest if guest else '')
        relative=str(base/name);directory=checked_path(studio,relative)
        if directory.exists():raise HTTPException(409,'Папка на диске уже существует; выбери другое название')
        directory.mkdir(parents=True)
        for group in GROUPS[body.kind]:checked_path(studio,str(Path(relative)/group)).mkdir()
        character_id=body.character_id
        if body.kind=='character' and not character_id:
            character_id=nid
            row=db.execute('SELECT state FROM projects WHERE id=?',(common['source_project_id'],)).fetchone();state=json.loads(row['state'])
            state.setdefault('characters',[]).append({'id':character_id,'name':body.title.strip(),'identity':{'species':'','face':'','hair':'','eyes':'','costume':'','negative':''},'profiles':{}})
            db.execute('UPDATE projects SET state=?,updated_at=? WHERE id=?',(json.dumps(state,ensure_ascii=False),studio.now(),common['source_project_id']))
        db.execute('INSERT INTO production_nodes VALUES(?,?,?,?,?,?,?,?,?,?,?)',(nid,pid,body.parent_id,body.kind,body.title.strip(),number,body.guest.strip(),relative,body.notes,character_id,studio.now()))
    write_text(studio,str(Path(relative)/NOTE_FILES[body.kind]),f'# {body.title.strip()}\n\n'+(f'Гость: {body.guest.strip()}\n\n' if guest else '')+body.notes+'\n')
    return node(studio,pid,nid)


class NewProduction(BaseModel):
    title:str=Field(min_length=1,max_length=75)
    source_project_id:str|None=None


class NewNode(BaseModel):
    kind:str
    parent_id:str|None=None
    title:str=Field(min_length=1,max_length=75)
    guest:str=Field(default='',max_length=75)
    number:int|None=Field(default=None,ge=0,le=9999)
    notes:str=Field(default='',max_length=30000)
    character_id:str|None=None


class AssetAssignment(BaseModel):
    asset_id:str
    category:str|None=None


class ProjectLink(BaseModel):
    project_id:str


class Notes(BaseModel):
    notes:str=Field(max_length=30000)


def register(app,studio):
    @app.get('/api/projects/{project_id}/workspace-location')
    def workspace_location(project_id:str):
        studio.project(project_id)
        membership=link(studio,project_id)
        if not membership:return None
        info={'production_id':membership['production_id'],'production_title':membership['title'],'source_project_id':membership['source_project_id'],'series':None,'scene':None,'frame':None}
        current=membership['node_id']
        seen=set()
        while current and current not in seen:
            seen.add(current)
            item=node(studio,membership['production_id'],current)
            field={'series':'series','episode':'scene','frame':'frame'}.get(item['kind'])
            if field:info[field]={'id':item['id'],'title':item['title']}
            current=item['parent_id']
        return info

    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS productions(id TEXT PRIMARY KEY,title TEXT NOT NULL,folder TEXT NOT NULL UNIQUE,source_project_id TEXT NOT NULL,created_at TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS production_nodes(id TEXT PRIMARY KEY,production_id TEXT NOT NULL,parent_id TEXT,kind TEXT NOT NULL,title TEXT NOT NULL,number INTEGER NOT NULL,guest TEXT NOT NULL,relative_dir TEXT NOT NULL UNIQUE,notes TEXT NOT NULL,character_id TEXT,created_at TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS production_files(id TEXT PRIMARY KEY,production_id TEXT NOT NULL,node_id TEXT NOT NULL,asset_id TEXT,filename TEXT NOT NULL,relative_path TEXT NOT NULL,kind TEXT NOT NULL,created_at TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS production_links(project_id TEXT PRIMARY KEY,production_id TEXT NOT NULL,node_id TEXT UNIQUE)')

    @app.get('/api/productions')
    def listing():
        with studio.connect() as db:return [dict(r) for r in db.execute('SELECT * FROM productions ORDER BY created_at')]

    @app.post('/api/productions')
    def create(body:NewProduction):
        folder=safe_name(body.title)
        if checked_path(studio,folder).exists():raise HTTPException(409,'Общий проект с таким именем папки уже существует')
        source=body.source_project_id
        if source:studio.project(source)
        else:source=studio.save_project(studio.Project(title=body.title+' — библиотека',state={'characters':[],'style':{}}))['id']
        with studio.connect() as db:
            if db.execute('SELECT 1 FROM production_links WHERE project_id=?',(source,)).fetchone():raise HTTPException(409,'Этот проект уже относится к общему проекту')
            pid=uuid.uuid4().hex
            db.execute('INSERT INTO productions VALUES(?,?,?,?,?)',(pid,body.title.strip(),folder,source,studio.now()))
            db.execute('INSERT INTO production_links VALUES(?,?,NULL)',(source,pid))
        for group in ROOT_GROUPS.values():checked_path(studio,str(Path(folder)/group)).mkdir(parents=True)
        write_text(studio,str(Path(folder)/'README.md'),f'# {body.title}\n\n01_Персонажи — общие образы и референсы.\n02_Локации — общие места действия.\n03_Серии — номер, название и гость; внутри эпизоды-сцены, раскадровки и кадры.\n\nОригиналы студии сохранены в backend/library. Здесь находятся организованные копии с метаданными.\n')
        write_text(studio,str(Path(folder)/'ПРОЕКТ.json'),json.dumps(production(studio,pid),ensure_ascii=False,indent=2))
        state=studio.project(source)['state']
        write_text(studio,str(Path(folder)/'БИБЛИЯ_МИРА.json'),json.dumps(state.get('style',{}),ensure_ascii=False,indent=2))
        for character in state.get('characters',[]):
            create_node(studio,pid,NewNode(kind='character',title=character['name'],character_id=character['id']))
            sync_character(studio,source,character['id'])
        return production(studio,pid)

    @app.get('/api/productions/{pid}')
    def tree(pid:str):
        info=production(studio,pid)
        with studio.connect() as db:
            children=[dict(r) for r in db.execute('SELECT * FROM production_nodes WHERE production_id=? ORDER BY number,title',(pid,))]
            linked=[dict(r) for r in db.execute('SELECT * FROM production_links WHERE production_id=?',(pid,))]
        return {**info,'absolute_path':str(checked_path(studio,info['folder'])),'nodes':children,'links':linked}

    @app.post('/api/productions/{pid}/nodes')
    def new_node(pid:str,body:NewNode):
        info=create_node(studio,pid,body)
        if info['kind']=='character':sync_character(studio,production(studio,pid)['source_project_id'],info['character_id'])
        return info

    @app.get('/api/productions/{pid}/nodes/{nid}')
    def contents(pid:str,nid:str):
        info=node(studio,pid,nid)
        with studio.connect() as db:files=[dict(r) for r in db.execute('SELECT * FROM production_files WHERE node_id=? ORDER BY relative_path',(nid,))]
        common=production(studio,pid)
        character=next((c for c in studio.project(common['source_project_id'])['state'].get('characters',[]) if c['id']==info['character_id']),None) if info['kind']=='character' else None
        return {**info,'character':character,'source_project_id':common['source_project_id'],'absolute_path':str(checked_path(studio,info['relative_dir'])),'groups':GROUPS[info['kind']],'files':[{**f,'url':'/api/production-files/'+f['id']} for f in files]}

    @app.get('/api/productions/{pid}/nodes/{nid}/reference-card')
    def reference_card(pid:str,nid:str):
        info=node(studio,pid,nid)
        if info['kind']!='character':raise HTTPException(400,'Выбери персонажа')
        from backend import character_voice
        character_voice.document(studio,info)
        return FileResponse(checked_path(studio,str(Path(info['relative_dir'])/'РЕФЕРЕНС_КАРТА.md')),filename='РЕФЕРЕНС_КАРТА.md')

    @app.put('/api/productions/{pid}/nodes/{nid}/notes')
    def notes(pid:str,nid:str,body:Notes):
        target=node(studio,pid,nid)
        write_text(studio,str(Path(target['relative_dir'])/NOTE_FILES[target['kind']]),f'# {target["title"]}\n\n'+body.notes+'\n')
        with studio.connect() as db:db.execute('UPDATE production_nodes SET notes=? WHERE id=?',(body.notes,nid))
        if target['kind']=='character':
            from backend import character_voice
            character_voice.document(studio,node(studio,pid,nid))
        return {'saved':True}

    @app.post('/api/productions/{pid}/nodes/{nid}/assets')
    def assign(pid:str,nid:str,body:AssetAssignment):return {'file_id':copy_asset(studio,pid,nid,body.asset_id,body.category)}

    @app.post('/api/productions/{pid}/nodes/{nid}/link-project')
    def attach(pid:str,nid:str,body:ProjectLink):
        target=node(studio,pid,nid)
        if target['kind']!='frame':raise HTTPException(400,'Проект студии привязывается к кадру')
        studio.project(body.project_id)
        with studio.connect() as db:
            old=db.execute('SELECT * FROM production_links WHERE project_id=?',(body.project_id,)).fetchone()
            if old and (old['production_id']!=pid or old['node_id'] not in (None,nid)):raise HTTPException(409,'Проект уже связан с другим кадром или общим проектом')
            if db.execute('SELECT 1 FROM production_links WHERE node_id=? AND project_id<>?',(nid,body.project_id)).fetchone():raise HTTPException(409,'Кадр уже связан с другим проектом студии')
            db.execute('INSERT INTO production_links VALUES(?,?,?) ON CONFLICT(project_id) DO UPDATE SET node_id=excluded.node_id',(body.project_id,pid,nid))
        sync_project(studio,body.project_id)
        return {'project_id':body.project_id}

    @app.post('/api/productions/{pid}/nodes/{nid}/open-project')
    def open_frame(pid:str,nid:str):
        target=node(studio,pid,nid)
        if target['kind']!='frame':raise HTTPException(400,'Открыть в студии можно папку кадра')
        with studio.connect() as db:existing=db.execute('SELECT project_id FROM production_links WHERE node_id=?',(nid,)).fetchone()
        if existing:
            with studio.connect() as db:
                if db.execute('SELECT 1 FROM project_archives WHERE project_id=?',(existing['project_id'],)).fetchone():raise HTTPException(409,'Тестовый проект в архиве. Восстановление доступно в настройках.')
            return {'project_id':existing['project_id']}
        common=production(studio,pid);source=studio.project(common['source_project_id'])['state']
        state={'brief':target['notes'],'prompts':{},'parameters':{},'characters':source.get('characters',[]),'selectedCharacter':source.get('selectedCharacter',''),'style':source.get('style',{})}
        project_id=studio.save_project(studio.Project(title=common['title']+' / '+target['title'],state=state))['id']
        return attach(pid,nid,ProjectLink(project_id=project_id))

    @app.post('/api/productions/{pid}/sync')
    def sync(pid:str):
        production(studio,pid)
        with studio.connect() as db:projects=db.execute('SELECT project_id FROM production_links WHERE production_id=?',(pid,)).fetchall()
        for item in projects:sync_project(studio,item['project_id'])
        return {'saved':True,'projects':len(projects)}

    @app.post('/api/productions/{pid}/nodes/{nid}/upload')
    async def import_file(pid:str,nid:str,category:str=Form(...),file:UploadFile=File(...)):
        target=node(studio,pid,nid)
        if category not in GROUPS[target['kind']]:raise HTTPException(400,'Неизвестный раздел папки')
        extension=Path(file.filename or '').suffix.lower()
        if extension not in EXTENSIONS:raise HTTPException(415,'Разрешены изображения, видео, звук, PDF, TXT, MD, JSON и SRT')
        content=await file.read(200*1024*1024+1)
        if len(content)>200*1024*1024:raise HTTPException(413,'Лимит файла — 200 МБ')
        kind='image' if extension in {'.png','.jpg','.jpeg','.webp'} else ('video' if extension in {'.mp4','.mov','.webm'} else ('audio' if extension in {'.mp3','.wav','.m4a'} else 'document'))
        image_info=None
        if kind=='image':
            if len(content)>20*1024*1024:raise HTTPException(413,'Лимит изображения — 20 МБ')
            image_info=studio.inspect_image(content)
        fid=uuid.uuid4().hex;name=safe_name(Path(file.filename or 'Файл').stem)+extension
        relative=str(Path(target['relative_dir'])/category/(fid[:8]+'_'+name))
        path=checked_path(studio,relative);path.write_bytes(content)
        with studio.connect() as db:
            asset_id=None
            if kind in {'image','video','audio'}:
                common=production(studio,pid)
                bound=db.execute('SELECT project_id FROM production_links WHERE node_id=?',(nid,)).fetchone()
                owner=bound['project_id'] if bound else common['source_project_id']
                asset_id=fid;canonical=fid+extension
                studio.LIBRARY_ROOT.mkdir(parents=True,exist_ok=True);(studio.LIBRARY_ROOT/canonical).write_bytes(content)
                metadata={**(image_info or {}),'kind':kind,'provider':'local_import','original_name':name,'request':{'payload':{'task_type':'local-reference','input':{'prompt':''}}}}
                if target['kind']=='character' and kind=='image':metadata.update(character_id=target['character_id'],character_status='reference')
                db.execute('INSERT INTO library_assets VALUES(?,?,?,?,?,?,?,?)',(fid,'import-'+fid,owner,0,canonical,'',json.dumps(metadata,ensure_ascii=False),studio.now()))
                if target['kind']=='character' and kind=='image':
                    directory=studio.char_directory(common['source_project_id'],target['character_id'],'real_references');directory.mkdir(parents=True,exist_ok=True);(directory/canonical).write_bytes(content)
                    db.execute('INSERT INTO character_assets VALUES(?,?,?,?,?,?,?,?,?,?)',(fid,common['source_project_id'],target['character_id'],'real_references','',canonical,name,'','Загружено в общую папку персонажа',studio.now()))
            db.execute('INSERT INTO production_files VALUES(?,?,?,?,?,?,?,?)',(fid,pid,nid,asset_id,name,relative,kind,studio.now()))
        if target['kind']=='character' and kind=='image':
            from backend import character_voice
            character_voice.document(studio,target)
        return {'id':fid,'url':'/api/production-files/'+fid}

    @app.get('/api/production-files/{fid}')
    def read_file(fid:str):
        with studio.connect() as db:row=db.execute('SELECT * FROM production_files WHERE id=?',(fid,)).fetchone()
        if not row:raise HTTPException(404,'Файл не найден')
        path=checked_path(studio,row['relative_path'])
        if not path.is_file():raise HTTPException(404,'Файл отсутствует на диске')
        return FileResponse(path,filename=row['filename'],content_disposition_type='inline' if row['kind'] in {'image','video','audio'} else 'attachment')
