"""Доступ из облака и с телефона.

Включается переменными окружения (иначе студия остаётся строго локальной):
  STUDIO_REMOTE_HOSTS     — публичные имена через запятую, например studio.example.com
  STUDIO_ACCESS_PASSWORD  — пароль входа, не короче 12 символов
  STUDIO_TRUSTED_PROXIES  — адреса proxy (IP или CIDR) через запятую, которым можно верить
                            forwarded-заголовки; пусто = не доверяем никому
  STUDIO_TRUSTED_PROXY_HOPS — сколько ходов proxy между клиентом и студией (по умолчанию —
                            столько, сколько адресов в STUDIO_TRUSTED_PROXIES)
Снаружи (не loopback) каждый запрос требует подписанную cookie studio_auth, которую выдаёт /api/login.
Пароль хранится только в окружении сервера; попытки входа ограничены. HTTPS обеспечивает обратный
прокси (см. docs/CLOUD_DEPLOY.md); cookie получает флаг Secure, когда прокси сообщает https.
"""
import hashlib
import hmac
import ipaddress
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

COOKIE = 'studio_auth'
LIFETIME = 14 * 24 * 3600
MAX_FAILS = 5
WINDOW = 300
LOOPBACK = {'127.0.0.1', 'localhost', '::1'}
PUBLIC_PATHS = {'/api/health', '/api/login', '/api/logout', '/login'}
TRUSTED_PROXIES_ENV = 'STUDIO_TRUSTED_PROXIES'
TRUSTED_HOPS_ENV = 'STUDIO_TRUSTED_PROXY_HOPS'
_fails = defaultdict(deque)


def config():
    hosts = {h.strip().lower() for h in os.environ.get('STUDIO_REMOTE_HOSTS', '').split(',') if h.strip()}
    password = os.environ.get('STUDIO_ACCESS_PASSWORD', '')
    if hosts and len(password) < 12:
        raise RuntimeError('STUDIO_ACCESS_PASSWORD должен быть не короче 12 символов, когда включён удалённый доступ')
    return hosts, password


def enabled():
    return bool(config()[0])


def allowed_host(hostname):
    return (hostname or '').lower() in config()[0]


TAILSCALE_NET = ipaddress.ip_network('100.64.0.0/10')  # адреса Tailscale (частная сеть между своими устройствами)


def private_ip(host):
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address in TAILSCALE_NET


def allowed_origin(origin):
    hosts = config()[0]
    if any(origin == f'https://{h}' for h in hosts):
        return True
    # Домашняя сеть по HTTP: только частные IP-адреса из списка, например http://192.168.8.253:8000
    parsed = urlparse(origin)
    return parsed.scheme == 'http' and (parsed.hostname or '').lower() in hosts and private_ip(parsed.hostname)         and parsed.port in (None, 8000, 5173)


def _key(password):
    return hashlib.sha256(('studio-auth:' + password).encode()).digest()


def make_cookie(password, now=None):
    expires = int((now or time.time()) + LIFETIME)
    nonce = secrets.token_hex(8)
    data = f'{expires}.{nonce}'
    return data + '.' + hmac.new(_key(password), data.encode(), hashlib.sha256).hexdigest()


def valid_cookie(value, password, now=None):
    try:
        expires, nonce, signature = value.split('.')
        expected = hmac.new(_key(password), f'{expires}.{nonce}'.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected) and int(expires) >= (now or time.time())
    except (ValueError, AttributeError):
        return False


def _parse_ip(value):
    """IP-адрес из peer-адреса или forwarded-заголовка; None, если это не адрес."""
    text = (value or '').strip()
    if not text:
        return None
    if text.startswith('[') and ']' in text:
        text = text[1:text.index(']')]
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        host, _, port = text.rpartition(':')
        if not host or not port.isdigit() or not 0 < int(port) <= 65535:
            return None
        try:
            addr = ipaddress.ip_address(host)
        except ValueError:
            return None
    return getattr(addr, 'ipv4_mapped', None) or addr


def trusted_proxies():
    """Доверенные proxy (IP или CIDR). Пустой список — forwarded-заголовки не доверяем никому."""
    networks = []
    for item in os.environ.get(TRUSTED_PROXIES_ENV, '').split(','):
        item = item.strip()
        if not item:
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            addr = _parse_ip(item)
            if addr is None:
                raise RuntimeError(f'{TRUSTED_PROXIES_ENV}: неверный адрес proxy: {item!r}')
            networks.append(ipaddress.ip_network(addr))
    return networks


def trusted_hops():
    """Сколько ходов proxy стоит между клиентом и студией."""
    raw = os.environ.get(TRUSTED_HOPS_ENV, '').strip()
    if not raw:
        return max(1, len(trusted_proxies()))
    try:
        hops = int(raw)
    except ValueError:
        raise RuntimeError(f'{TRUSTED_HOPS_ENV} должен быть целым числом')
    if hops < 1:
        raise RuntimeError(f'{TRUSTED_HOPS_ENV} должен быть не меньше 1')
    return hops


def client_ip(request: Request, proxies=None, hops=None):
    """Адрес клиента, по которому считаются неудачные попытки входа.

    По умолчанию берётся адрес непосредственного соединения: клиент подделывает
    X-Forwarded-For, поэтому forwarded-заголовок сам по себе не является идентификатором.
    Цепочка читается только когда запрос пришёл от явно доверенного proxy
    (STUDIO_TRUSTED_PROXIES) и берётся с конца: адрес, записанный последним доверенным
    ходом, — это клиент, всё что дописал клиент слева, игнорируется.
    """
    peer = request.client.host if request.client else '?'
    networks = trusted_proxies() if proxies is None else proxies
    if not networks:
        return peer
    peer_addr = _parse_ip(peer)
    if peer_addr is None or not any(peer_addr in net for net in networks):
        return peer
    limit = trusted_hops() if hops is None else hops
    chain = []
    for part in (request.headers.get('x-forwarded-for') or '').split(','):
        addr = _parse_ip(part)
        if addr is not None:
            chain.append(addr)
    if len(chain) < limit:
        return peer
    return str(chain[-limit])


def is_loopback(request: Request):
    """Заголовок Host подделывается любым устройством сети, поэтому локальным запрос считается,
    только если и Host, и адрес клиента loopback ('testclient' бывает лишь в тестах)."""
    host = request.headers.get('host', '').rsplit(':', 1)[0].strip('[]').lower()
    client = request.client.host if request.client else ''
    return host in LOOPBACK and client in LOOPBACK | {'testclient'}


LOGIN_PAGE = '''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Вход · AI Workflow Studio</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0E0F12;color:#ECE8DF;font-family:system-ui,sans-serif}
form{width:min(340px,90vw);display:grid;gap:12px}input,button{font:inherit;padding:12px;border-radius:10px;border:1px solid #3A3F4A;background:#16181D;color:inherit}
button{background:#F2B134;color:#17130A;border:0;font-weight:600}p{color:#E27B7B;min-height:1.2em;margin:0}</style></head>
<body><form id="f"><h1>Студия</h1><input id="p" type="password" placeholder="Пароль" autocomplete="current-password" autofocus>
<button>Войти</button><p id="m"></p></form><script>
f.onsubmit=async e=>{e.preventDefault();const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:p.value})});
if(r.ok)location.href='/';else m.textContent=(await r.json().catch(()=>({}))).detail||'Не удалось войти'}</script></body></html>'''


class Login(BaseModel):
    password: str


def register(app, studio=None):
    config()  # неверная настройка останавливает запуск сразу
    trusted_proxies()  # неверный список proxy тоже останавливает запуск сразу
    trusted_hops()
    @app.middleware('http')
    async def gate(request: Request, call_next):
        if not enabled() or is_loopback(request):
            return await call_next(request)
        path = request.url.path
        if path in PUBLIC_PATHS:
            return await call_next(request)
        _, password = config()
        if valid_cookie(request.cookies.get(COOKIE, ''), password):
            return await call_next(request)
        # Машинный вызов (n8n Cloud, веб-интеграция): токен в заголовке вместо cookie входа.
        from backend import service_auth
        if service_auth.machine_ok(request):
            return await call_next(request)
        if path.startswith('/api/'):
            return JSONResponse({'detail': 'Нужен вход в студию'}, status_code=401)
        return RedirectResponse('/login')

    @app.get('/login')
    def login_page():
        return HTMLResponse(LOGIN_PAGE, headers={'Cache-Control': 'no-store'})

    @app.post('/api/login')
    def login(body: Login, request: Request):
        if not enabled():
            return JSONResponse({'detail': 'Удалённый доступ не включён'}, status_code=404)
        ip = client_ip(request)
        now = time.time()
        recent = _fails[ip]
        while recent and recent[0] < now - WINDOW:
            recent.popleft()
        if len(recent) >= MAX_FAILS:
            return JSONResponse({'detail': 'Слишком много попыток. Подожди несколько минут.'}, status_code=429)
        _, password = config()
        if not hmac.compare_digest(body.password.encode(), password.encode()):
            recent.append(now)
            return JSONResponse({'detail': 'Неверный пароль'}, status_code=401)
        response = JSONResponse({'ok': True})
        secure = request.headers.get('x-forwarded-proto', request.url.scheme) == 'https'
        response.set_cookie(COOKIE, make_cookie(password), max_age=LIFETIME, httponly=True, secure=secure,
                            samesite='lax', path='/')
        return response

    @app.post('/api/logout')
    def logout():
        response = JSONResponse({'ok': True})
        response.delete_cookie(COOKIE, path='/')
        return response


def mount_frontend(app, root: Path):
    """Отдаёт собранный интерфейс с того же адреса, что и API (нужно для облака)."""
    from fastapi.staticfiles import StaticFiles
    dist = root / 'frontend' / 'dist'
    if dist.is_dir():
        app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
