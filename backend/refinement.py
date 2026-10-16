"""Local originals and strict edit briefs for the native imagegen chat."""
import hashlib
import json
import uuid
from fastapi import File, Form, HTTPException, UploadFile

PRESERVE_VISUAL = '''Edit Image 1 as the original target; do not recreate it from its old prompt.
Change only the explicitly requested detail. Preserve all unrelated features:
every character's identity, face, age, expression, anatomy, hair, clothing and silhouette;
composition, framing, perspective, background, object positions, lighting, shadows,
reflections, palette, materials, textures and rendering style.
If the requested change affects a listed property, change only the necessary part.
Use Image 2, when supplied, only as a reference for the requested detail. Do not copy
its face, background, style or other unrelated properties into the original.
Keep the original aspect ratio and resolution where supported; do not upscale to claim
better native output. Do not add objects, text, accessories or a beauty pass.
These are editing constraints, not a guarantee of pixel-identical preservation.'''

def edit_context(studio,body):
    studio.project(body.project_id)
    if body.use_scene or not body.source_asset_id or not body.edit_instruction.strip():
        raise HTTPException(400,'Выбери оригинал и опиши правку')
    if body.reference_asset_id==body.source_asset_id:
        raise HTTPException(400,'Дополнительный референс должен отличаться от оригинала')
    references=[];source_metadata={}
    for aid,role in ((body.source_asset_id,'edit_target'),(body.reference_asset_id,'detail_reference')):
        if not aid:continue
        with studio.connect() as db:
            row=studio.production_folders.accessible_asset(studio,db,aid,body.project_id)
        if not row:raise HTTPException(404,'Исходник не найден в библиотеке этого проекта')
        metadata=json.loads(row['metadata'])
        if metadata.get('kind') in {'video','audio','document'}:raise HTTPException(400,'В «Допилить» принимаются только изображения')
        path=(studio.LIBRARY_ROOT/row['filename']).resolve()
        if not path.is_relative_to(studio.LIBRARY_ROOT.resolve()) or not path.is_file():
            raise HTTPException(404,'Файл изображения отсутствует')
        references.append({'label':f'Image {len(references)+1}','role':role,'asset_id':aid,'local_path':str(path),'url':row['source_url']})
        if role=='edit_target':source_metadata={'provider':metadata.get('provider'),'width':metadata.get('width'),'height':metadata.get('height'),'character_id':metadata.get('character_id')}
    return {'brief':body.edit_instruction.strip(),'intent':'edit','target_model':body.target,
            'preservation_contract':PRESERVE_VISUAL,'references':references,
            'source_metadata':source_metadata,'rules_version':studio.RULES_VERSION}

def register(app,studio):
    @app.post('/api/library/import-image')
    async def import_image(project_id:str=Form(...),file:UploadFile=File(...)):
        studio.project(project_id)
        content=await file.read(20*1024*1024+1)
        if len(content)>20*1024*1024:raise HTTPException(413,'Максимальный размер — 20 МБ')
        info=studio.inspect_image(content)
        aid=uuid.uuid4().hex
        filename=aid+{'PNG':'.png','JPEG':'.jpg','WEBP':'.webp'}[info['format']]
        studio.LIBRARY_ROOT.mkdir(parents=True,exist_ok=True)
        path=studio.LIBRARY_ROOT/filename;path.write_bytes(content)
        metadata={**info,'kind':'image','provider':'local_import','original_name':(file.filename or '')[:200],
                  'sha256':hashlib.sha256(content).hexdigest(),'role':'user_reference',
                  'request':{'payload':{'task_type':'local-reference','input':{'prompt':''}}}}
        try:
            with studio.connect() as db:
                db.execute('INSERT INTO library_assets VALUES(?,?,?,?,?,?,?,?)',(aid,'import-'+aid,project_id,0,filename,'',json.dumps(metadata,ensure_ascii=False),studio.now()))
                row=db.execute('SELECT * FROM library_assets WHERE id=?',(aid,)).fetchone()
        except Exception:
            path.unlink(missing_ok=True)
            raise
        studio.production_folders.sync_asset(studio,aid)
        return studio.library_record(row)
