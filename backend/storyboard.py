"""Persistent storyboard view over production_nodes; append-only screenplay import."""
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field
from backend import production_folders as folders


def parse_script(text):
    scenes=[]
    preamble=[]
    for line in text.splitlines():
        match=re.match(r'^\s*(?:#{1,3}\s*)?Сцена\s+(\d+)\s*[.\-—:)]?\s*(.*)$',line,re.I)
        if match:
            title=match[2].strip() or f'Сцена {match[1]}'
            if len(title)>75:raise HTTPException(400,'Название сцены должно быть не длиннее 75 символов')
            folders.safe_name(title)
            scenes.append({'title':title,'lines':[]})
        elif scenes:scenes[-1]['lines'].append(line)
        else:preamble.append(line)
    if not scenes:raise HTTPException(400,'Добавь заголовки «Сцена 1 — Название», «Сцена 2 — Название»')
    if len(scenes)>100:raise HTTPException(400,'За один импорт можно добавить до 100 сцен')
    scenes[0]['lines']=preamble+scenes[0]['lines']
    for s in scenes:
        s['notes']='\n'.join(s.pop('lines')).strip()
        if len(s['notes'])>30000:raise HTTPException(400,'Текст одной сцены превышает 30000 символов')
    if len({s['title'].casefold() for s in scenes})!=len(scenes):
        raise HTTPException(400,'Названия сцен должны различаться; добавь короткое уточнение')
    return scenes


def series(db,pid,sid):
    row=db.execute("SELECT * FROM production_nodes WHERE id=? AND production_id=? AND kind='series'",(sid,pid)).fetchone()
    if not row:raise HTTPException(404,'Серия не найдена в выбранном проекте')
    return dict(row)


def snapshot(db,pid,sid):
    parent=series(db,pid,sid)
    nodes=[dict(r) for r in db.execute('''SELECT * FROM production_nodes WHERE production_id=? AND
        (parent_id=? OR parent_id IN (SELECT id FROM production_nodes WHERE production_id=? AND parent_id=? AND kind='episode'))
        ORDER BY number,id''',(pid,sid,pid,sid))]
    imports=db.execute('SELECT request_id,script FROM storyboard_imports WHERE series_id=? ORDER BY rowid DESC LIMIT 1',(sid,)).fetchone()
    entity_states=[dict(r) for r in db.execute('SELECT node_id,data FROM production_entity_state WHERE node_id IN (SELECT id FROM production_nodes WHERE production_id=?) ORDER BY node_id',(pid,))]
    revision=hashlib.sha256(json.dumps([parent,nodes,imports['request_id'] if imports else None,entity_states],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return parent,nodes,imports['script'] if imports else parent['notes'],revision


class ImportScript(BaseModel):
    script:str=Field(min_length=1,max_length=200000)
    base_revision:str=Field(min_length=64,max_length=64)
    request_id:str=Field(min_length=8,max_length=100,pattern=r'^[a-zA-Z0-9_-]+$')
    mode:Literal['append','update']='append'
    scene_node_ids:list[str|None]=Field(default_factory=list,max_length=100)


class Reorder(BaseModel):
    base_revision:str=Field(min_length=64,max_length=64)
    parent_id:str=Field(min_length=1,max_length=100)  # серия (порядок сцен) или сцена серии (порядок кадров)
    node_ids:list[str]=Field(min_length=1,max_length=500)


def reorder(db,pid,sid,body):
    """Новый порядок детей одного родителя: меняется только number. Папки на диске не переименовываются."""
    _,nodes,_,revision=snapshot(db,pid,sid)
    if body.base_revision!=revision:raise HTTPException(409,'Доска изменилась. Обнови её и повтори перестановку.')
    scenes={n['id'] for n in nodes if n['kind']=='episode' and n['parent_id']==sid}
    if body.parent_id==sid:kind='episode'
    elif body.parent_id in scenes:kind='frame'
    else:raise HTTPException(400,'Порядок меняется внутри серии или сцены этой серии')
    siblings=[n for n in nodes if n['kind']==kind and n['parent_id']==body.parent_id]
    known={n['id'] for n in siblings}
    if len(set(body.node_ids))!=len(body.node_ids) or not set(body.node_ids)<=known:
        raise HTTPException(400,'Список содержит повтор или карточку другого родителя')
    # Скрытые с доски кадры (архивные рабочие проекты) остаются после видимых в прежнем порядке.
    rest=[n['id'] for n in sorted(siblings,key=lambda n:(n['number'],n['id'])) if n['id'] not in body.node_ids]
    order=list(body.node_ids)+rest
    current={n['id']:n['number'] for n in siblings}
    for number,nid in enumerate(order,1):
        if current[nid]!=number:db.execute('UPDATE production_nodes SET number=? WHERE id=?',(number,nid))
    return order


def register(app,studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS storyboard_imports(
                request_id TEXT PRIMARY KEY,series_id TEXT NOT NULL,payload_hash TEXT NOT NULL,
                script TEXT NOT NULL,node_ids TEXT NOT NULL,created_at TEXT NOT NULL)''')

    @app.get('/api/productions/{pid}/series/{sid}/storyboard')
    def board(pid:str,sid:str):
        with studio.connect() as db:
            parent,nodes,script,revision=snapshot(db,pid,sid)
            scenes=[]
            for item in nodes:
                if item['kind']!='episode' or item['parent_id']!=sid:continue
                frames=[]
                for frame in nodes:
                    if frame['kind']!='frame' or frame['parent_id']!=item['id']:continue
                    files=[{**dict(r),'url':'/api/production-files/'+r['id']} for r in db.execute("SELECT * FROM production_files WHERE node_id=? AND kind IN ('image','video') ORDER BY created_at DESC,id DESC",(frame['id'],))]
                    bound=db.execute('SELECT project_id FROM production_links WHERE production_id=? AND node_id=?',(pid,frame['id'])).fetchone()
                    if bound and db.execute('SELECT 1 FROM project_archives WHERE project_id=?',(bound['project_id'],)).fetchone():continue
                    from backend.production_entities import state
                    _,selection,_=state(db,pid,frame['id'])
                    frames.append({**frame,'files':files,'selection':selection,'project_id':bound['project_id'] if bound else None})
                from backend.production_entities import state
                _,selection,_=state(db,pid,item['id'])
                scenes.append({**item,'frames':frames,'selection':selection})
        return {'series':parent,'scenes':scenes,'script':script,'revision':revision}

    @app.put('/api/productions/{pid}/series/{sid}/storyboard/order')
    def set_order(pid:str,sid:str,body:Reorder):
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            order=reorder(db,pid,sid,body)
            _,_,_,revision=snapshot(db,pid,sid)
        return {'order':order,'revision':revision}

    @app.post('/api/productions/{pid}/series/{sid}/storyboard/preview')
    def preview(pid:str,sid:str,body:ImportScript):
        with studio.connect() as db:
            _,nodes,_,revision=snapshot(db,pid,sid)
        if body.base_revision!=revision:raise HTTPException(409,'Доска изменилась. Обнови её перед импортом; исходный текст сохранён в поле.')
        scenes=parse_script(body.script)
        existing={n['title'].casefold() for n in nodes if n['parent_id']==sid}
        return {'scenes':scenes,'conflicts':[s['title'] for s in scenes if s['title'].casefold() in existing] if body.mode=='append' else [],
                'existing':[{'id':n['id'],'title':n['title'],'notes':n['notes']} for n in nodes if n['parent_id']==sid and n['kind']=='episode']}

    @app.post('/api/productions/{pid}/series/{sid}/storyboard/import')
    def import_script(pid:str,sid:str,body:ImportScript):
        scenes=parse_script(body.script)
        payload=body.script if body.mode=='append' else json.dumps([body.script,body.mode,body.scene_node_ids],ensure_ascii=False)
        digest=hashlib.sha256(payload.encode()).hexdigest()
        created_dirs=[]
        created_files=[]
        updated_notes=[]
        try:
            with studio.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                parent=series(db,pid,sid)
                previous=db.execute('SELECT * FROM storyboard_imports WHERE request_id=?',(body.request_id,)).fetchone()
                if previous:
                    if previous['series_id']!=sid or previous['payload_hash']!=digest:raise HTTPException(409,'Этот идентификатор импорта уже использован для другого текста')
                    return {'node_ids':json.loads(previous['node_ids']),'replayed':True,'file_warning':None}
                _,nodes,_,revision=snapshot(db,pid,sid)
                if body.base_revision!=revision:raise HTTPException(409,'Доска изменилась. Обнови её и повторно проверь импорт.')
                mapping=body.scene_node_ids if body.mode=='update' else [None]*len(scenes)
                if len(mapping)!=len(scenes):raise HTTPException(400,'Сопоставь каждую сцену с существующей или выбери создание новой')
                mapped=[nid for nid in mapping if nid]
                allowed={n['id'] for n in nodes if n['parent_id']==sid and n['kind']=='episode'}
                if len(set(mapped))!=len(mapped) or not set(mapped)<=allowed:raise HTTPException(400,'Сопоставление содержит повтор или сцену другой серии')
                titles={n['title'].casefold() for n in nodes if n['parent_id']==sid and n['id'] not in mapped}
                if any(s['title'].casefold() in titles for s in scenes):raise HTTPException(409,'Сцена с таким названием уже существует. Импорт добавляет новые сцены; существующие редактируются отдельно.')
                number=max((n['number'] for n in nodes if n['parent_id']==sid),default=0)
                ids=[]
                added=0
                for index,s in enumerate(scenes):
                    if mapping[index]:
                        nid=mapping[index]
                        old=next(n for n in nodes if n['id']==nid)
                        db.execute('UPDATE production_nodes SET title=?,notes=? WHERE id=?',(s['title'],s['notes'],nid))
                        updated_notes.append((str(Path(old['relative_dir'])/folders.NOTE_FILES['episode']),f'# {s["title"]}\n\n{s["notes"]}\n'))
                        ids.append(nid)
                        continue
                    added+=1
                    nid=uuid.uuid4().hex
                    relative=Path(parent['relative_dir'])/'02_Эпизоды'/f'{number+added:03d}_{folders.safe_name(s["title"])}'
                    directory=folders.checked_path(studio,relative)
                    if directory.exists():raise HTTPException(409,'Папка сцены уже существует на диске. Проверь её перед импортом.')
                    directory.mkdir();created_dirs.append(directory)
                    for group in folders.GROUPS['episode']:
                        child=directory/group;child.mkdir();created_dirs.append(child)
                    note=directory/folders.NOTE_FILES['episode']
                    created_files.append(note)
                    note.write_text(f'# {s["title"]}\n\n{s["notes"]}\n',encoding='utf-8')
                    db.execute('''INSERT INTO production_nodes(id,production_id,parent_id,kind,title,number,guest,relative_dir,notes,character_id,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(nid,pid,sid,'episode',s['title'],number+added,'',str(relative),s['notes'],None,studio.now()))
                    ids.append(nid)
                db.execute('INSERT INTO storyboard_imports(request_id,series_id,payload_hash,script,node_ids,created_at) VALUES(?,?,?,?,?,?)',
                           (body.request_id,sid,digest,body.script,json.dumps(ids),studio.now()))
        except Exception:
            # Only paths created by this attempt, checked under PRODUCTIONS_ROOT; no recursive removal.
            for path in reversed(created_files):
                folders.checked_path(studio,path.relative_to(studio.PRODUCTIONS_ROOT.resolve())).unlink(missing_ok=True)
            for path in reversed(created_dirs):
                folders.checked_path(studio,path.relative_to(studio.PRODUCTIONS_ROOT.resolve())).rmdir()
            raise
        warning=None
        try:
            for relative,text in updated_notes:folders.write_text(studio,relative,text)
            folders.write_text(studio,str(Path(parent['relative_dir'])/'01_Сценарий'/f'СЦЕНАРИЙ_{body.request_id}.md'),body.script)
        except OSError:
            warning='Сцены и исходный сценарий сохранены в БД, но копию сценария на диске записать не удалось.'
        return {'node_ids':ids,'replayed':False,'file_warning':warning}
