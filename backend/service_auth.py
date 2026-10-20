"""Машинный доступ к API студии для внешних исполнителей (n8n Cloud, веб-интеграция).

Токены живут только в окружении сервера. Формат STUDIO_SERVICE_TOKENS:

    STUDIO_SERVICE_TOKENS=токен1:проект-1,проект-2;токен2:*

Зона `*` — все проекты студии. Токен без зоны не выдаётся: пустой список игнорируется.

Машинный вызов отличается от браузерного: у него нет cookie studio_auth и сессии студии,
поэтому доступ проверяется по заголовку `Authorization: Bearer <токен>`. Зона токена
записывается в request.state.service_scopes, и каждый платный или приёмочный эндпоинт
обязан сам проверить, что проект входит в зону."""
import hashlib
import hmac
import os

from fastapi import HTTPException

ENV = 'STUDIO_SERVICE_TOKENS'

# Машинный токен не должен открывать весь API: только приёмочный контур и учёт
# расходов n8n-агентов. Генерация, медиа и настройки остаются за браузерной
# сессией владельца.
ALLOWED_PREFIXES = ('/api/qa/', '/api/n8n/spend/')


def tokens():
    """{токен: {проект, ...}} из окружения сервера."""
    out = {}
    for entry in os.environ.get(ENV, '').split(';'):
        entry = entry.strip()
        if not entry or ':' not in entry:
            continue
        token, _, scope = entry.partition(':')
        token = token.strip()
        scopes = {part.strip() for part in scope.split(',') if part.strip()}
        if token and scopes:
            out[token] = scopes
    return out


def bearer(request):
    value = request.headers.get('authorization') or ''
    return value[7:].strip() if value.lower().startswith('bearer ') else ''


def identify(request):
    """(зона токена, отпечаток) или (None, None)."""
    token = bearer(request)
    if not token:
        return None, None
    for known, scopes in tokens().items():
        if hmac.compare_digest(token, known):
            return scopes, hashlib.sha256(known.encode()).hexdigest()[:8]
    return None, None


def allowed(scopes, project_id):
    return bool(scopes) and ('*' in scopes or project_id in scopes)


def machine_ok(request):
    """Токен есть и путь входит в разрешённые для машинного доступа.

    Токен открывает только приёмочный контур: /api/qa/*. Всё остальное — генерация,
    медиа, настройки — остаётся за браузерной сессией владельца."""
    scopes, _ = identify(request)
    if not scopes:
        return False
    return request.url.path.startswith(ALLOWED_PREFIXES)


def require_token(request):
    """Машинный токен обязателен: без него запрос не проходит даже к самому эндпоинту."""
    scopes, fingerprint = identify(request)
    if not scopes:
        raise HTTPException(401, 'Нужен машинный токен студии: Authorization: Bearer <токен>')
    return fingerprint


def require_project(request, project_id):
    """Машинный доступ к проекту: 401 без токена, 403 если проект вне зоны."""
    fingerprint = require_token(request)
    scopes, _ = identify(request)
    if not allowed(scopes, project_id):
        raise HTTPException(403, 'Токен не имеет доступа к этому проекту')
    return fingerprint
