"""Explicit temporary image upload for video references, separate from generation."""
import asyncio
import base64
import time
import re
import math
from typing import Literal
from urllib.parse import urlsplit
import httpx
from fastapi import Header, HTTPException
from pydantic import BaseModel

DOCS='https://app.piapi.ai/docs/tools/file-upload'
UPLOAD_URL='https://upload.theapi.app/api/ephemeral_resource'
LOCKS={}
FREE_DOCS='https://tempfile.org/api'
FREE_UPLOAD_URL='https://tempfile.org/api/upload/local'


class Approval(BaseModel):
    approved: bool = False
    provider: Literal['tempfile','piapi'] = 'tempfile'


def public_https(url):
    """Публичная ссылка для провайдера: только https с хостом. Метка inline-base64 у результатов GPT Image ссылкой не считается."""
    parts=urlsplit(url) if isinstance(url,str) else None
    return url if parts and parts.scheme=='https' and parts.hostname else None


def reference_url(studio,row):
    with studio.connect() as db:
        cached=db.execute('SELECT url,expires_at FROM public_references WHERE asset_id=?',(row['id'],)).fetchone()
    return public_https(cached['url'] if cached and cached['expires_at']>time.time() else row['source_url'])


async def upload(key,filename,content):
    try:
        async with httpx.AsyncClient(timeout=60,follow_redirects=False) as client:
            response=await client.post(UPLOAD_URL,headers={'x-api-key':key},json={'file_name':filename,'file_data':base64.b64encode(content).decode('ascii')})
        if response.status_code==403:raise HTTPException(403,'Временная загрузка PiAPI требует Creator/Pro. Генерация не запускалась.')
        if response.status_code!=200:raise HTTPException(502,'Не удалось загрузить референс в PiAPI; генерация не запускалась')
        value=response.json()
        url=(value.get('data') or {}).get('url','')
        if value.get('code')!=200 or urlsplit(url).scheme!='https' or not urlsplit(url).hostname:raise ValueError()
        return url
    except (httpx.RequestError,ValueError):
        raise HTTPException(502,'Ответ о загрузке референса не получен; автоматического повтора и генерации нет')


async def upload_free(filename,content):
    """No credentials are sent to the free host; construct its documented direct URL."""
    try:
        async with httpx.AsyncClient(timeout=90,follow_redirects=False) as client:
            response=await client.post(FREE_UPLOAD_URL,data={'expiryHours':'24'},files={'files':(filename,content)})
        if response.status_code==429:raise HTTPException(429,'TempFile временно ограничил загрузки. Подожди и повтори вручную; генерация не запускалась.')
        if response.status_code!=200:raise HTTPException(502,'TempFile не принял файл; генерация не запускалась')
        value=response.json()
        files=value.get('files') or []
        if value.get('success') is not True or len(files)!=1:raise ValueError()
        entry=files[0];file_id=entry.get('id','')
        if not isinstance(file_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',file_id):raise ValueError()
        expires=float(entry['expiryTime'])/1000
        if not math.isfinite(expires) or expires<=time.time()+300:raise ValueError()
        return {'url':f'https://tempfile.org/{file_id}/download','expires_at':min(expires-300,time.time()+23*3600)}
    except (httpx.RequestError,ValueError,TypeError,KeyError,AttributeError):
        raise HTTPException(502,'Ответ TempFile о загрузке не получен или некорректен; автоматического повтора и генерации нет')


def register(app,studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS public_references(asset_id TEXT PRIMARY KEY,url TEXT NOT NULL,expires_at REAL NOT NULL)')
            if 'provider' not in {r['name'] for r in db.execute('PRAGMA table_info(public_references)')}:
                db.execute("ALTER TABLE public_references ADD COLUMN provider TEXT NOT NULL DEFAULT 'piapi'")

    @app.post('/api/library/{asset_id}/upload-reference')
    async def publish(asset_id:str,body:Approval,x_api_key:str|None=Header(default=None)):
        if not body.approved:raise HTTPException(400,'Подтверди передачу оригинала в выбранное временное хранилище')
        async with LOCKS.setdefault(asset_id,asyncio.Lock()):
            with studio.connect() as db:
                asset=db.execute('SELECT * FROM library_assets WHERE id=?',(asset_id,)).fetchone()
                cached=db.execute('SELECT * FROM public_references WHERE asset_id=?',(asset_id,)).fetchone()
            if not asset:raise HTTPException(404,'Изображение не найдено')
            if cached and cached['provider']==body.provider and cached['expires_at']>time.time():return {'url':cached['url'],'expires_at':cached['expires_at'],'provider':body.provider,'cached':True}
            path=(studio.LIBRARY_ROOT/asset['filename']).resolve()
            if not path.is_relative_to(studio.LIBRARY_ROOT.resolve()) or not path.is_file():raise HTTPException(404,'Оригинал отсутствует')
            content=path.read_bytes()
            if len(content)>20*1024*1024:raise HTTPException(413,'Для загрузки референса нужен оригинал до 20 МБ')
            if body.provider=='piapi' and len(content)>7_500_000:raise HTTPException(413,'Для загрузки PiAPI нужен оригинал до 7,5 МБ (до 10 МБ в Base64). Уменьши отдельную копию изображения.')
            studio.inspect_image(content)
            if body.provider=='tempfile':
                result=await upload_free(path.name,content);url=result['url'];expires=result['expires_at']
            else:
                url=await upload(studio.get_key(x_api_key),path.name,content);expires=time.time()+23*3600
            with studio.connect() as db:
                db.execute('INSERT INTO public_references(asset_id,url,expires_at,provider) VALUES(?,?,?,?) ON CONFLICT(asset_id) DO UPDATE SET url=excluded.url,expires_at=excluded.expires_at,provider=excluded.provider',(asset_id,url,expires,body.provider))
            return {'url':url,'expires_at':expires,'provider':body.provider,'cached':False}
