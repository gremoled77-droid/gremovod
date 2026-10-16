"""Scene cast, entity editor revisions and explicit selected media over production nodes."""
import hashlib
import json
from pathlib import Path
from fastapi import HTTPException
from pydantic import BaseModel,Field
from backend import production_folders as folders


def state(db,pid,nid):
    row=db.execute('SELECT * FROM production_nodes WHERE production_id=? AND id=?',(pid,nid)).fetchone()
    if not row:raise HTTPException(404,'Карточка не найдена в этом проекте')
    node=dict(row)
    saved=db.execute('SELECT data FROM production_entity_state WHERE node_id=?',(nid,)).fetchone()
    data={'character_node_ids':[],'location_node_id':None,'selected_image_file_id':None,'selected_video_file_id':None,**(json.loads(saved['data']) if saved else {})}
    parent_snapshot=None
    if node['kind']=='character':
        owner=db.execute('SELECT p.state FROM projects p JOIN productions c ON c.source_project_id=p.id WHERE c.id=?',(pid,)).fetchone()
        profile=next((c for c in json.loads(owner['state']).get('characters',[]) if c['id']==node['character_id']),None) if owner else None
        parent_snapshot=profile
        if profile:
            primary=db.execute("SELECT id FROM production_files WHERE node_id=? AND asset_id=? ORDER BY relative_path",(nid,profile.get('working_asset_id'))).fetchone()
            data['selected_image_file_id']=primary['id'] if primary else None
    if node['kind']=='frame':
        parent=db.execute('SELECT notes FROM production_nodes WHERE id=?',(node['parent_id'],)).fetchone()
        parent_data=db.execute('SELECT data FROM production_entity_state WHERE node_id=?',(node['parent_id'],)).fetchone()
        parent_snapshot=[parent['notes'] if parent else '',parent_data['data'] if parent_data else None]
    reference_files=[dict(r) for r in db.execute("""SELECT f.id,f.asset_id,f.relative_path FROM production_files f
        LEFT JOIN library_assets a ON a.id=f.asset_id WHERE f.node_id=? AND f.kind='image'
        AND (json_extract(a.metadata,'$.provider')='local_import' OR f.relative_path LIKE '%Референсы%' OR f.relative_path LIKE '%Основной_образ%' OR f.relative_path LIKE '%Исходники%') ORDER BY f.id""",(nid,))]
    revision=hashlib.sha256(json.dumps([node,data,parent_snapshot,reference_files],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return node,data,revision


class Update(BaseModel):
    base_revision:str=Field(min_length=64,max_length=64)
    notes:str=Field(max_length=30000)
    character_node_ids:list[str]=Field(default_factory=list,max_length=100)
    location_node_id:str|None=None
    selected_image_file_id:str|None=None
    selected_video_file_id:str|None=None


def validate(db,pid,node,body):
    if node['kind']!='episode' and (body.character_node_ids or body.location_node_id):raise HTTPException(400,'Состав закрепляется за сценой')
    if len(set(body.character_node_ids))!=len(body.character_node_ids):raise HTTPException(400,'Персонаж выбран дважды')
    for nid,kind in [(nid,'character') for nid in body.character_node_ids]+([(body.location_node_id,'location')] if body.location_node_id else []):
        if not db.execute('SELECT 1 FROM production_nodes WHERE id=? AND production_id=? AND kind=?',(nid,pid,kind)).fetchone():raise HTTPException(400,'Персонаж или локация не принадлежат проекту')
    for fid,kind in [(body.selected_image_file_id,'image'),(body.selected_video_file_id,'video')]:
        if fid and not db.execute('SELECT 1 FROM production_files WHERE id=? AND node_id=? AND production_id=? AND kind=?',(fid,node['id'],pid,kind)).fetchone():raise HTTPException(400,'Выбранный файл другого типа или не относится к этой карточке')


def context(studio,body):
    with studio.connect() as db:
        node,data,revision=state(db,body.production_id,body.production_node_id)
        common=db.execute('SELECT * FROM productions WHERE id=?',(body.production_id,)).fetchone()
        bound=db.execute('SELECT project_id FROM production_links WHERE node_id=?',(node['id'],)).fetchone()
        owner=bound['project_id'] if bound else common['source_project_id']
        if body.project_id!=owner:raise HTTPException(400,'Задание должно принадлежать владельцу карточки')
        if body.entity_revision!=revision:raise HTTPException(409,'Карточка изменилась. Обнови её перед отправкой')
        related=[node]
        scene_data=data
        if node['kind']=='frame':
            scene_node,scene_data,_=state(db,body.production_id,node['parent_id'])
            related.append(scene_node)
        for nid in scene_data['character_node_ids']+([scene_data['location_node_id']] if scene_data['location_node_id'] else []):
            item=db.execute('SELECT * FROM production_nodes WHERE id=? AND production_id=?',(nid,body.production_id)).fetchone()
            if item:related.append(dict(item))
        refs=[];seen=set()
        for item in related:
            _,selection,_=state(db,body.production_id,item['id'])
            files=db.execute("SELECT * FROM production_files WHERE node_id=? AND kind='image' ORDER BY created_at,id",(item['id'],)).fetchall()
            # Prefer the explicit approved image; older output variants are not identity references.
            primary=selection['selected_image_file_id']
            imported={r['id'] for r in db.execute("SELECT f.id FROM production_files f JOIN library_assets a ON a.id=f.asset_id WHERE f.node_id=? AND json_extract(a.metadata,'$.provider')='local_import'",(item['id'],))}
            chosen=[f for f in files if f['id']==primary] if primary else [f for f in files if f['id'] in imported or any(part in Path(f['relative_path']).parts for part in ['01_Основной_образ','02_Референсы','01_Референсы','01_Исходники'])]
            for f in chosen:
                path=folders.checked_path(studio,f['relative_path'])
                if not path.is_file() or str(path) in seen:continue
                seen.add(str(path));refs.append({'label':studio.reference_label(body.target,len(refs)+1),'local_path':str(path),'role':item['kind'],'note':item['title'],'asset_id':f['asset_id']})
        limit=studio.MODEL_SPECS[body.target]['max_refs']
        if len(refs)>limit:raise HTTPException(400,'Слишком много референсов. Выбери основные изображения в карточках')
        from backend import visual_plan
        style=visual_plan.rules_text(db,body.production_id,node['id'])
        character=None
        if node['kind']=='character':
            project=db.execute('SELECT state FROM projects WHERE id=?',(common['source_project_id'],)).fetchone()
            character=next((c for c in json.loads(project['state']).get('characters',[]) if c['id']==node['character_id']),None)
    return {'brief':node['notes']+('\n\n'+style if style else '')+'\n\nЗАДАНИЕ: '+body.entity_instruction,'references':refs,'character':character,
            'scene':{'participants':[{'id':n['id'],'kind':n['kind'],'name':n['title'],'description':n['notes']} for n in related]},
            'entity':{'production_id':body.production_id,'node_id':node['id'],'kind':node['kind'],'title':node['title'],'character_id':node.get('character_id'),'revision':revision},
            'capabilities':studio.MODEL_SPECS[body.target],'rules_version':studio.RULES_VERSION,
            'preservation':'Preserve character identity, selected location geometry, seating and reference design. Make only the requested changes.'}


def deliver(studio,item,asset_id):
    recipient=json.loads(item['request']).get('context',{}).get('entity')
    if not recipient:return
    node=folders.node(studio,recipient['production_id'],recipient['node_id'])
    category={'episode':'02_Раскадровка','frame':'02_Изображения','character':'03_Архив','location':'02_Изображения'}.get(node['kind'])
    if category:folders.copy_asset(studio,recipient['production_id'],node['id'],asset_id,category)


def video_anchor(studio,project_id,references):
    if not project_id:return
    with studio.connect() as db:
        linked=db.execute("SELECT l.production_id,l.node_id FROM production_links l JOIN production_nodes n ON n.id=l.node_id WHERE l.project_id=? AND n.kind='frame'",(project_id,)).fetchone()
        if not linked:return
        _,selection,_=state(db,linked['production_id'],linked['node_id'])
        anchor=db.execute("SELECT a.* FROM production_files f JOIN library_assets a ON a.id=f.asset_id WHERE f.id=? AND f.node_id=? AND f.kind='image'",(selection['selected_image_file_id'],linked['node_id'])).fetchone()
    if not anchor:raise HTTPException(400,'Перед видео выбери основное фото в карточке кадра на доске раскадровки')
    from backend import reference_upload
    url=reference_upload.reference_url(studio,anchor)
    if not references or not url or references[0]!=url:raise HTTPException(400,'Первым референсом видео должно быть выбранное основное фото этого кадра. Подготовь для него публичную ссылку.')


def register(app,studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS production_entity_state(node_id TEXT PRIMARY KEY,data TEXT NOT NULL,updated_at TEXT NOT NULL)')

    @app.post('/api/productions/{pid}/nodes/{nid}/jobs/{jid}/deliver')
    def retry_delivery(pid:str,nid:str,jid:str):
        with studio.connect() as db:row=db.execute('SELECT * FROM native_chat_jobs WHERE id=?',(jid,)).fetchone()
        if not row:raise HTTPException(404,'Задание не найдено')
        recipient=json.loads(row['request']).get('context',{}).get('entity',{})
        if recipient.get('node_id')!=nid or recipient.get('production_id')!=pid or not row['asset_id']:raise HTTPException(400,'Результат не относится к карточке')
        deliver(studio,row,row['asset_id'])
        return {'saved':True}

    @app.get('/api/productions/{pid}/nodes/{nid}/editor')
    def editor(pid:str,nid:str):
        with studio.connect() as db:
            node,data,revision=state(db,pid,nid)
            common=db.execute('SELECT * FROM productions WHERE id=?',(pid,)).fetchone()
            bound=db.execute('SELECT project_id FROM production_links WHERE node_id=?',(nid,)).fetchone()
            owner=bound['project_id'] if bound else common['source_project_id']
            files=[{**dict(r),'url':'/api/production-files/'+r['id']} for r in db.execute('SELECT * FROM production_files WHERE node_id=? ORDER BY created_at DESC,id DESC',(nid,))]
            jobs=[]
            for r in db.execute('SELECT * FROM native_chat_jobs WHERE project_id IN (?,?) ORDER BY created_at DESC',(owner,common['source_project_id'])):
                snapshot=json.loads(r['request']).get('context',{}).get('entity',{})
                if snapshot.get('node_id')==nid:
                    jobs.append({'id':r['id'],'status':r['status'],'operation':r['operation'],'target':r['target'],'prompt':r['prompt'],'asset_id':r['asset_id'],'message':r['message'],'outdated':snapshot.get('revision')!=revision})
            catalog=[dict(r) for r in db.execute("SELECT id,title,kind FROM production_nodes WHERE production_id=? AND kind IN ('character','location') ORDER BY title",(pid,))]
        character=None
        if node['kind']=='character':character=next((c for c in studio.project(common['source_project_id'])['state'].get('characters',[]) if c['id']==node['character_id']),None)
        return {'node':node,'data':data,'revision':revision,'files':files,'jobs':jobs[:30],'catalogue':catalog,'owner_project_id':owner,'character':character,'groups':folders.GROUPS[node['kind']]}

    @app.put('/api/productions/{pid}/nodes/{nid}/editor')
    def save(pid:str,nid:str,body:Update):
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            node,old,revision=state(db,pid,nid)
            if revision!=body.base_revision:raise HTTPException(409,'Карточка изменилась в другом окне. Черновик сохранён; обнови данные перед повторным сохранением')
            validate(db,pid,node,body)
            data=body.model_dump(exclude={'base_revision','notes'})
            db.execute('UPDATE production_nodes SET notes=? WHERE id=?',(body.notes,nid))
            db.execute('INSERT INTO production_entity_state(node_id,data,updated_at) VALUES(?,?,?) ON CONFLICT(node_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',(nid,json.dumps(data),studio.now()))
            # A final VIDEO take drives the economic outcome. A keyframe is not a finished-video use.
            if node['kind']=='frame' and old['selected_video_file_id']!=data['selected_video_file_id']:
                oldfile=db.execute('SELECT asset_id FROM production_files WHERE id=?',(old['selected_video_file_id'],)).fetchone()
                newfile=db.execute('SELECT asset_id FROM production_files WHERE id=?',(data['selected_video_file_id'],)).fetchone()
                if oldfile and oldfile['asset_id']:
                    still=db.execute("SELECT 1 FROM production_entity_state s JOIN production_files f ON f.id=json_extract(s.data,'$.selected_video_file_id') WHERE f.asset_id=? AND s.node_id<>?",(oldfile['asset_id'],nid)).fetchone()
                    if not still:db.execute("UPDATE asset_outcomes SET decision='undecided',updated_at=? WHERE asset_id=? AND decision='used'",(studio.now(),oldfile['asset_id']))
                if newfile and newfile['asset_id']:db.execute("INSERT INTO asset_outcomes(asset_id,decision,updated_at) VALUES(?,'used',?) ON CONFLICT(asset_id) DO UPDATE SET decision='used',updated_at=excluded.updated_at",(newfile['asset_id'],studio.now()))
        warning=None
        try:
            folders.write_text(studio,str(Path(node['relative_dir'])/folders.NOTE_FILES[node['kind']]),f'# {node["title"]}\n\n{body.notes}\n')
            folders.write_text(studio,str(Path(node['relative_dir'])/'КАРТОЧКА.json'),json.dumps(data,ensure_ascii=False,indent=2))
        except OSError:warning='БД сохранена, но копию карточки на диске записать не удалось'
        return {'saved':True,'file_warning':warning}
