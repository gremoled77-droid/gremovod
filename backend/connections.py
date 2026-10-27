"""Server-only credentials and read-only provider checks. Never return upstream bodies."""
import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, HTTPException

ROOT=Path(__file__).resolve().parent.parent
PROVIDERS={
    'piapi':{'name':'PiAPI','env':'PIAPI_API_KEY','file':'PIAPI_API_KEY.txt','url':'https://api.piapi.ai/account/info','header':'X-API-Key','docs':'https://piapi.ai/docs/account-info-api'},
    'openai':{'name':'OpenAI','env':'OPENAI_API_KEY','file':'OPENAI_API_KEY.txt','url':'https://api.openai.com/v1/models','header':'Authorization','docs':'https://developers.openai.com/api/reference/resources/models/methods/list'},
    'elevenlabs':{'name':'ElevenLabs','env':'ELEVENLABS_API_KEY','file':'ELEVENLABS_API_KEY.txt','url':'https://api.elevenlabs.io/v1/user/subscription','header':'xi-api-key','docs':'https://elevenlabs.io/docs/api-reference/user/subscription/get'},
    'fish':{'name':'Fish Audio','env':'FISH_AUDIO_API_KEY','file':'FISH_AUDIO_API_KEY.txt','url':'https://api.fish.audio/wallet/self/api-credit','header':'Authorization','docs':'https://docs.fish.audio/api-reference/openapi.json'},
    'kie':{'name':'KIE','env':'KIE_API_KEY','file':'KIE_API_KEY.txt','url':'https://api.kie.ai/api/v1/chat/credit','header':'Authorization','docs':'https://docs.kie.ai/common-api/get-account-credits'},
}
ELEVENLABS_LEGACY_FILE=Path(os.getenv('ELEVENLABS_KEY_FILE') or str(Path.home()/'Documents'/'!GREM TAXI'/'.secrets'/'elevenlabs-api-key.txt'))
# Ключ KIE, сохранённый kie-access/connect.ps1: DPAPI текущего пользователя Windows (ConvertFrom-SecureString, hex).
KIE_DPAPI_FILES=[Path(p) for p in (os.getenv('KIE_DPAPI_FILE'),) if p]+[ROOT/'kie-access'/'api-key.dpapi',
                 Path.home()/'Documents'/'ChatGPT'/'AMOCRM'/'kie-access'/'api-key.dpapi']

def dpapi_decrypt(blob:bytes)->bytes:
    """CryptUnprotectData для текущего пользователя. Только Windows."""
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_char))]
    buffer=ctypes.create_string_buffer(blob,len(blob))
    source=Blob(len(blob),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_char)));result=Blob()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source),None,None,None,None,0,ctypes.byref(result)):
        raise OSError('CryptUnprotectData failed')
    try: return ctypes.string_at(result.pbData,result.cbData)
    finally: ctypes.windll.kernel32.LocalFree(result.pbData)

def dpapi_key(paths):
    for path in paths:
        try: text=path.read_text(encoding='utf-8-sig').strip()
        except FileNotFoundError: continue
        except (OSError,UnicodeError): raise HTTPException(400,'Не удалось прочитать файл ключа')
        if os.name!='nt': raise HTTPException(400,'Ключ DPAPI расшифровывается только в Windows')
        try: return dpapi_decrypt(bytes.fromhex(text)).decode('utf-16-le').strip(),path
        except (OSError,ValueError,UnicodeError): raise HTTPException(400,'Не удалось расшифровать ключ DPAPI: нужен тот же пользователь Windows')
    return '',None
CHECKS={}
router=APIRouter()

def credential(provider, header=None, file_override=None):
    if provider not in PROVIDERS: raise HTTPException(400,'Неизвестный провайдер')
    spec=PROVIDERS[provider]
    key=(header or '').strip() or os.getenv(spec['env'],'').strip()
    source='заголовок запроса' if (header or '').strip() else 'переменная окружения'
    if not key:
        paths=[file_override or ROOT/spec['file']]
        if provider=='elevenlabs': paths.append(ELEVENLABS_LEGACY_FILE)
        for path in paths:
            try: key=path.read_text(encoding='utf-8-sig').strip()
            except FileNotFoundError: continue
            except (OSError,UnicodeError): raise HTTPException(400,'Не удалось прочитать файл ключа')
            if key:
                source='файл проекта' if path==paths[0] else 'файл проекта «Гремовод»'
                break
    if not key and provider=='kie':
        key,_=dpapi_key(KIE_DPAPI_FILES)
        source='kie-access (DPAPI)'
    if not key: raise HTTPException(400,'Ключ не настроен: '+spec['file']+(' или kie-access/api-key.dpapi' if provider=='kie' else ''))
    if not key.isascii() or any(not 32<ord(c)<127 for c in key): raise HTTPException(400,'Ключ должен быть одной строкой ASCII без пробелов')
    return key,source

def provider_key(provider, header=None): return credential(provider,header)[0]

def connection_info(provider):
    spec=PROVIDERS[provider]
    base={'id':provider,'name':spec['name'],'filename':spec['file'],'docs':spec['docs']}
    try: key,source=credential(provider)
    except HTTPException as exc:
        return {**base,'configured':False,'status':'not_configured','message':exc.detail,'checked_at':None}
    digest=hashlib.sha256(key.encode()).hexdigest()
    cached=CHECKS.get(provider,{})
    if cached.get('_digest')!=digest: cached={}
    return {**base,'configured':True,'source':source,'status':'unverified','message':'Ключ настроен; соединение ещё не проверено','checked_at':None,
            **{k:v for k,v in cached.items() if k!='_digest'}}

@router.get('/api/connections')
def list_connections(): return [connection_info(p) for p in PROVIDERS]

@router.post('/api/connections/{provider}/check')
async def check_connection(provider:str):
    if provider not in PROVIDERS: raise HTTPException(404,'Неизвестный провайдер')
    info=connection_info(provider)
    if not info['configured']: return info
    key,_=credential(provider)
    spec=PROVIDERS[provider]
    value='Bearer '+key if spec['header']=='Authorization' else key
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'_digest':hashlib.sha256(key.encode()).hexdigest()}
    try:
        # Fixed GET endpoints only. Redirects intentionally disabled for credentialed requests.
        async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
            response=await client.get(spec['url'],headers={spec['header']:value})
        text=response.text
        if response.status_code==403 and ('1010' in text or 'browser_signature_banned' in text):
            result.update(status='blocked',message='Cloudflare 1010. Обратись в поддержку PiAPI; автоматических повторов нет.')
        elif response.status_code in (401,403):
            result.update(status='denied',message='Доступ отклонён. Проверь ключ и разрешение на чтение аккаунта.')
        elif response.status_code==429:
            result.update(status='rate_limited',message='Сервис ограничил частоту запросов. Проверь позднее.')
        elif response.is_success:
            try: data=response.json()
            except ValueError: data=None
            if not isinstance(data,dict) or data.get('code',200) not in (0,200):
                result.update(status='error',message='Неожиданный ответ API; подключение не подтверждено.')
            else:
                result.update(status='connected',message='Доступ к API подтверждён. Генерации не запускались.')
        else: result.update(status='error',message=f'Сервис вернул HTTP {response.status_code}.')
    except httpx.RequestError:
        result.update(status='unreachable',message='Нет соединения с сервисом: проверь сеть и доступность API.')
    CHECKS[provider]=result
    return connection_info(provider)
