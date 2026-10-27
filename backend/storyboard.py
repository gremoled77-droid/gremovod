"""Persistent storyboard view over production_nodes; append-only screenplay import."""
import hashlib
import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from backend import production_folders as folders
from backend.director_contracts import (
    LOCKED_PREDICATES,
    PREDICATES,
    ShotContract,
    check_asset_references,
    check_chain,
    check_continuity,
    check_coverage,
    check_shots,
    sort_issues,
)


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


# --- Контракты кадра --------------------------------------------------------
# Контракт хранится рядом с доской, но отдельно от неё: доска может быть
# переработана целиком, а контракт кадра — подписан автором. Решения человека
# не теряются при перерисовке сцены.

class ContractSave(BaseModel):
    model_config=ConfigDict(extra='forbid')
    base_revision:int=Field(ge=0)
    contract:ShotContract


class ContractCheck(BaseModel):
    model_config=ConfigDict(extra='forbid')
    contract:ShotContract


def board_frames(db,pid,sid):
    """Кадры серии в порядке доски: сцена, затем кадр внутри сцены."""
    _,nodes,_,_=snapshot(db,pid,sid)
    by_parent={}
    for node in nodes:
        by_parent.setdefault(node['parent_id'],[]).append(node)
    scenes=sorted(by_parent.get(sid,[]),key=lambda n:(n['number'],n['id']))
    frames=[]
    for scene in scenes:
        if scene['kind']!='episode':
            continue
        for frame in by_parent.get(scene['id'],[]):
            if frame['kind']=='frame':
                frames.append((scene,frame))
    frames.sort(key=lambda pair:(pair[0]['number'],pair[1]['number'],pair[1]['id']))
    return frames


def plan_events(db,sid):
    """Карточки плана серии как реестр событий сценария."""
    try:
        row=db.execute('SELECT data FROM story_plans WHERE series_id=?',(sid,)).fetchone()
    except sqlite3.OperationalError:
        return []
    cards=json.loads(row['data']).get('cards',[]) if row else []
    from backend import story_plan
    return story_plan.plan_events(cards,sid)


def director_assets(db,pid):
    """ID ассетов библиотеки проекта — только их можно ссылать в контракте."""
    row=db.execute('SELECT source_project_id FROM productions WHERE id=?',(pid,)).fetchone()
    if not row:
        return set()
    return {r['id'] for r in db.execute('SELECT id FROM library_assets WHERE project_id=?',(row['source_project_id'],))}


def stored_contracts(db,sid):
    """Сохранённые контракты серии: контракт и его ревизия."""
    found={}
    for row in db.execute('SELECT shot_id,data,revision FROM shot_contracts WHERE series_id=?',(sid,)):
        try:
            contract=ShotContract.model_validate(json.loads(row['data']))
        except (ValueError,ValidationError):
            # Повреждённая запись не должна ронять весь раздел режиссура.
            continue
        found[contract.shot_id]=(contract,row['revision'])
    return found


def contract_issues(shots,events,assets):
    """Замечания по контрактам: непрерывность, ссылки на события и ассеты."""
    found=[]
    for shot in shots:
        found.extend(check_continuity(shot))
        found.extend(check_shots(events,[shot]))
    found.extend(check_chain(shots))
    found.extend(check_asset_references(shots,assets))
    return sort_issues(found)


def shot_of_path(path,shots):
    """Кадр, к которому относится замечание: путь вида shots[2].…"""
    if not path.startswith('shots['):
        return None
    try:
        index=int(path.split(']',1)[0][6:])
    except ValueError:
        return None
    return shots[index].shot_id if 0<=index<len(shots) else None


def director_view(db,pid,sid):
    """Состояние режиссуры серии: контракты, события и замечания."""
    _,_,_,revision=snapshot(db,pid,sid)
    frames=board_frames(db,pid,sid)
    events=plan_events(db,sid)
    assets=director_assets(db,pid)
    stored=stored_contracts(db,sid)
    contracts=[]
    shots=[]
    for scene,frame in frames:
        entry=stored.get(frame['id'])
        contract=entry[0] if entry else None
        contracts.append({
            'shot_id':frame['id'],
            'scene_id':scene['id'],
            'title':frame['title'],
            'number':f"{scene['number']}.{frame['number']}",
            'revision':entry[1] if entry else 0,
            'contract':contract.model_dump(mode='json') if contract else None,
        })
        if contract:
            shots.append(contract)
    issues=[]
    # Покрытие событий — свойство серии, а не одного кадра: оно показывается
    # в обзоре, но не блокирует сохранение отдельного контракта.
    for issue in sort_issues(contract_issues(shots,events,assets)+check_coverage(events,shots)):
        issues.append({**issue.model_dump(mode='json'),'shot_id':shot_of_path(issue.path,shots)})
    return {
        'board_revision':revision,
        'events':[event.model_dump(mode='json') for event in events],
        'contracts':contracts,
        'issues':issues,
        'predicates':PREDICATES,
        'locked_predicates':sorted(LOCKED_PREDICATES),
    }


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


class SendFrame(BaseModel):
    asset_id:str=Field(min_length=1,max_length=100)
    title:str=Field(min_length=1,max_length=75)


class SendFrames(BaseModel):
    base_revision:str=Field(min_length=64,max_length=64)
    request_id:str=Field(min_length=8,max_length=100,pattern=r'^[a-zA-Z0-9_-]+$')
    scene_id:str|None=None  # существующая сцена серии; иначе создаётся новая со scene_title
    scene_title:str|None=Field(default=None,min_length=1,max_length=75)
    frames:list[SendFrame]=Field(min_length=1,max_length=20)
    character_node_ids:list[str]=Field(default_factory=list,max_length=100)
    location_node_id:str|None=None


def send_check(db,pid,sid,body):
    """Всё, что можно проверить до создания папок: ревизия, сцена, названия, доступность картинок, состав."""
    _,nodes,_,revision=snapshot(db,pid,sid)
    if body.base_revision!=revision:raise HTTPException(409,'Доска изменилась. Обнови её и повтори отправку.')
    if bool(body.scene_id)==bool(body.scene_title):raise HTTPException(400,'Выбери существующую сцену или укажи название новой')
    scenes=[n for n in nodes if n['kind']=='episode' and n['parent_id']==sid]
    if body.scene_id:
        if body.scene_id not in {n['id'] for n in scenes}:raise HTTPException(400,'Сцена не относится к этой серии')
        taken={n['title'].casefold() for n in nodes if n['kind']=='frame' and n['parent_id']==body.scene_id}
    else:
        if body.scene_title.strip().casefold() in {n['title'].casefold() for n in scenes}:raise HTTPException(409,'Сцена с таким названием уже есть')
        folders.safe_name(body.scene_title)
        taken=set()
    titles=[f.title.strip().casefold() for f in body.frames]
    if len(set(titles))!=len(titles) or taken&set(titles):raise HTTPException(409,'Названия кадров должны различаться в пределах сцены')
    for f in body.frames:
        folders.safe_name(f.title)
        row=db.execute('SELECT a.metadata FROM library_assets a WHERE a.id=? AND a.project_id IN (SELECT project_id FROM production_links WHERE production_id=?)',(f.asset_id,pid)).fetchone()
        if not row:raise HTTPException(404,'Картинка не найдена в проектах этого общего проекта')
        if json.loads(row['metadata']).get('kind','image')!='image':raise HTTPException(400,'В кадры отправляются только изображения')
    if len(set(body.character_node_ids))!=len(body.character_node_ids):raise HTTPException(400,'Персонаж выбран дважды')
    for nid,kind in [(n,'character') for n in body.character_node_ids]+([(body.location_node_id,'location')] if body.location_node_id else []):
        if not db.execute('SELECT 1 FROM production_nodes WHERE id=? AND production_id=? AND kind=?',(nid,pid,kind)).fetchone():
            raise HTTPException(400,'Персонаж или локация не принадлежит этому общему проекту')


class OutlineFrame(BaseModel):
    title:str=Field(min_length=1,max_length=75)
    notes:str=Field(default='',max_length=5000)


class OutlineScene(BaseModel):
    title:str=Field(min_length=1,max_length=75)
    notes:str=Field(default='',max_length=30000)
    frames:list[OutlineFrame]=Field(min_length=1,max_length=20)


class Outline(BaseModel):
    base_revision:str=Field(min_length=64,max_length=64)
    request_id:str=Field(min_length=8,max_length=100,pattern=r'^[a-zA-Z0-9_-]+$')
    scenes:list[OutlineScene]=Field(min_length=1,max_length=20)


def outline_check(db,pid,sid,body):
    """Проверки до создания папок: ревизия, названия сцен и кадров, допустимость для имён папок."""
    _,nodes,_,revision=snapshot(db,pid,sid)
    if body.base_revision!=revision:raise HTTPException(409,'Доска изменилась. Обнови её и повтори добавление.')
    taken={n['title'].casefold() for n in nodes if n['kind']=='episode' and n['parent_id']==sid}
    names=[s.title.strip().casefold() for s in body.scenes]
    if len(set(names))!=len(names) or taken&set(names):raise HTTPException(409,'Названия сцен должны различаться и не совпадать с уже существующими')
    for scene in body.scenes:
        folders.safe_name(scene.title)
        titles=[f.title.strip().casefold() for f in scene.frames]
        if len(set(titles))!=len(titles):raise HTTPException(409,f'В сцене «{scene.title}» названия кадров должны различаться')
        for f in scene.frames:folders.safe_name(f.title)


def register(app,studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS storyboard_imports(
                request_id TEXT PRIMARY KEY,series_id TEXT NOT NULL,payload_hash TEXT NOT NULL,
                script TEXT NOT NULL,node_ids TEXT NOT NULL,created_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS shot_contracts(
                series_id TEXT NOT NULL,shot_id TEXT NOT NULL,data TEXT NOT NULL,
                revision INTEGER NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(series_id,shot_id))''')
            db.execute('''CREATE TABLE IF NOT EXISTS storyboard_sends(
                request_id TEXT PRIMARY KEY,series_id TEXT NOT NULL,payload_hash TEXT NOT NULL,
                result TEXT NOT NULL,created_at TEXT NOT NULL)''')

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

    @app.post('/api/productions/{pid}/series/{sid}/storyboard/frames')
    def send_frames(pid:str,sid:str,body:SendFrames):
        """«Отправить в раскадровку»: кадры из выбранных картинок, главный дубль и состав сцены. Повтор с тем же request_id ничего не дублирует."""
        from backend.production_entities import state as entity_state
        digest=hashlib.sha256(body.model_dump_json(exclude={'base_revision'}).encode()).hexdigest()
        with studio.connect() as db:
            previous=db.execute('SELECT * FROM storyboard_sends WHERE request_id=?',(body.request_id,)).fetchone()
            if previous:
                if previous['series_id']!=sid or previous['payload_hash']!=digest:raise HTTPException(409,'Этот идентификатор отправки уже использован для другого набора кадров')
                return {**json.loads(previous['result']),'replayed':True}
            series(db,pid,sid)
            send_check(db,pid,sid,body)
        scene_id=body.scene_id
        if not scene_id:
            scene_id=folders.create_node(studio,pid,folders.NewNode(kind='episode',parent_id=sid,title=body.scene_title.strip()))['id']
        frame_ids=[]
        for item in body.frames:
            frame=folders.create_node(studio,pid,folders.NewNode(kind='frame',parent_id=scene_id,title=item.title.strip()))
            file_id=folders.copy_asset(studio,pid,frame['id'],item.asset_id)
            with studio.connect() as db:
                db.execute('INSERT INTO production_entity_state(node_id,data,updated_at) VALUES(?,?,?) ON CONFLICT(node_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',
                           (frame['id'],json.dumps({'character_node_ids':body.character_node_ids,'location_node_id':body.location_node_id,'location_angle_file_id':None,'selected_image_file_id':file_id,'selected_video_file_id':None}),studio.now()))
            frame_ids.append(frame['id'])
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            _,cast,_=entity_state(db,pid,scene_id)
            cast['character_node_ids']=cast['character_node_ids']+[n for n in body.character_node_ids if n not in cast['character_node_ids']]
            if body.location_node_id:cast['location_node_id']=body.location_node_id
            db.execute('INSERT INTO production_entity_state(node_id,data,updated_at) VALUES(?,?,?) ON CONFLICT(node_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',
                       (scene_id,json.dumps(cast),studio.now()))
            result={'scene_id':scene_id,'frame_ids':frame_ids}
            db.execute('INSERT INTO storyboard_sends(request_id,series_id,payload_hash,result,created_at) VALUES(?,?,?,?,?)',
                       (body.request_id,sid,digest,json.dumps(result),studio.now()))
            revision=snapshot(db,pid,sid)[3]
        return {**result,'revision':revision,'replayed':False}

    @app.post('/api/productions/{pid}/series/{sid}/storyboard/outline')
    def add_outline(pid:str,sid:str,body:Outline):
        """Сцены и пустые кадры по плану (например, от GPT): без картинок, текст кадра в заметке. Повтор с тем же request_id ничего не дублирует."""
        digest=hashlib.sha256(body.model_dump_json(exclude={'base_revision'}).encode()).hexdigest()
        with studio.connect() as db:
            previous=db.execute('SELECT * FROM storyboard_sends WHERE request_id=?',(body.request_id,)).fetchone()
            if previous:
                if previous['series_id']!=sid or previous['payload_hash']!=digest:raise HTTPException(409,'Этот идентификатор уже использован для другого плана')
                return {**json.loads(previous['result']),'replayed':True}
            series(db,pid,sid)
            outline_check(db,pid,sid,body)
        scene_ids=[];frame_ids=[]
        for scene in body.scenes:
            node=folders.create_node(studio,pid,folders.NewNode(kind='episode',parent_id=sid,title=scene.title.strip(),notes=scene.notes))
            scene_ids.append(node['id'])
            for frame in scene.frames:
                frame_ids.append(folders.create_node(studio,pid,folders.NewNode(kind='frame',parent_id=node['id'],title=frame.title.strip(),notes=frame.notes))['id'])
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            result={'scene_ids':scene_ids,'frame_ids':frame_ids}
            db.execute('INSERT INTO storyboard_sends(request_id,series_id,payload_hash,result,created_at) VALUES(?,?,?,?,?)',
                       (body.request_id,sid,digest,json.dumps(result),studio.now()))
            revision=snapshot(db,pid,sid)[3]
        return {**result,'revision':revision,'replayed':False}

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

    @app.get('/api/productions/{pid}/series/{sid}/director/contracts')
    def director_contracts(pid:str,sid:str):
        with studio.connect() as db:
            series(db,pid,sid)
            return director_view(db,pid,sid)

    @app.post('/api/productions/{pid}/series/{sid}/director/contracts/check')
    def check_director_contract(pid:str,sid:str,body:ContractCheck):
        with studio.connect() as db:
            series(db,pid,sid)
            issues=contract_issues([body.contract],plan_events(db,sid),director_assets(db,pid))
        rows=[issue.model_dump(mode='json') for issue in issues]
        return {'issues':rows,'ok':not any(issue['severity']=='error' for issue in rows)}

    @app.put('/api/productions/{pid}/series/{sid}/director/contracts/{shot_id}')
    def save_director_contract(pid:str,sid:str,shot_id:str,body:ContractSave):
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            series(db,pid,sid)
            frames=board_frames(db,pid,sid)
            target=next((pair for pair in frames if pair[1]['id']==shot_id),None)
            if target is None:
                raise HTTPException(404,'Кадр не найден в этой серии')
            scene,_=target
            contract=body.contract
            if contract.shot_id!=shot_id:
                raise HTTPException(400,'ID контракта не совпадает с кадром')
            if contract.scene_id!=scene['id']:
                raise HTTPException(400,'Контракт привязан к другой сцене')
            row=db.execute('SELECT revision FROM shot_contracts WHERE series_id=? AND shot_id=?',(sid,shot_id)).fetchone()
            revision=row['revision'] if row else 0
            if body.base_revision!=revision:
                raise HTTPException(409,'Контракт изменился в другом окне. Обнови контракт перед сохранением.')
            events=plan_events(db,sid)
            assets=director_assets(db,pid)
            issues=contract_issues([contract],events,assets)
            blocking=[issue for issue in issues if issue.severity=='error']
            # Решение человека принимается, но утверждённым может быть только
            # контракт без ошибок: сначала правка, потом подпись.
            stored=contract.model_copy(update={'status':'draft'}) if blocking else contract
            data=json.dumps(stored.model_dump(mode='json'),ensure_ascii=False)
            db.execute('INSERT OR REPLACE INTO shot_contracts(series_id,shot_id,data,revision,updated_at) VALUES(?,?,?,?,?)',
                       (sid,shot_id,data,revision+1,studio.now()))
        return {'shot_id':shot_id,'revision':revision+1,'contract':stored.model_dump(mode='json'),
                'issues':[issue.model_dump(mode='json') for issue in issues],
                'downgraded':bool(blocking)}
