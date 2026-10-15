"""Bounded image downloads from provider output, without credential forwarding."""
import io
import ipaddress
import socket
from urllib.parse import urlsplit, urljoin
import httpx
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException

def check_public_url(url):
    try:
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):
            raise ValueError()
        addresses=socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses): raise ValueError()
    except (ValueError,OSError): raise HTTPException(400,'Изображение должно находиться на публичном HTTPS-сервере')

async def download_image(url, max_bytes=20*1024*1024):
    for _ in range(4):
        check_public_url(url)
        try:
            async with httpx.AsyncClient(timeout=45,follow_redirects=False) as client:
                async with client.stream('GET',url) as response:
                    if response.status_code in (301,302,303,307,308):
                        url=urljoin(url,response.headers.get('location',''))
                        continue
                    if response.status_code!=200: raise HTTPException(502,'Не удалось скачать результат. Ссылка могла истечь.')
                    content=bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content)>max_bytes: raise HTTPException(413,'Превышен лимит размера медиа')
            return bytes(content)
        except httpx.RequestError: raise HTTPException(502,'Ошибка загрузки результата. Генерация повторно не запускалась.')
    raise HTTPException(502,'Слишком много перенаправлений при загрузке изображения')

def inspect_image(content):
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in {'PNG','JPEG','WEBP'} or image.width*image.height>40_000_000:
                raise ValueError()
            info={'format':image.format,'width':image.width,'height':image.height}
            image.load()
            return info
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError):
        raise HTTPException(422,'Результат не является допустимым PNG, JPEG или WebP')

def output_urls(response,kind='image'):
    output=(response.get('data') or {}).get('output') or {}
    if not isinstance(output,dict): return []
    result=[]
    def collect(value):
        if isinstance(value,list):
            for item in value: collect(item)
        elif isinstance(value,dict): collect(value.get('url'))
        elif isinstance(value,str) and value.startswith('https://') and value not in result: result.append(value)
    fields=('video_urls','videos','video_url','url','video') if kind=='video' else ('image_urls','images','image_url','url','image')
    for field in fields: collect(output.get(field))
    return result

async def download_video(url):
    return await download_image(url,max_bytes=200*1024*1024)
