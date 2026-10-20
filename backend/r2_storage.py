"""Хранилище R2 (S3-совместимое, Cloudflare) для материалов студии: финальный ролик, кадры, аудио.

Зачем это в студии, а не в n8n: приёмочные материалы должны жить на сервере и отдаваться
неизменяемыми ссылками. n8n и внешние критики получают ссылку, а не «файл у кого-то на диске».

Настройки в окружении сервера:

    R2_ENDPOINT           https://<account_id>.r2.cloudflarestorage.com
    R2_BUCKET             имя бакета
    R2_ACCESS_KEY_ID      ключ R2 (R2 → Manage R2 API Tokens)
    R2_SECRET_ACCESS_KEY  секрет R2
    R2_PUBLIC_BASE_URL    публичный адрес бакета, если бакет открыт (https://assets.<домен>)

Подпись запросов — AWS Signature V4 с регионом `auto` и сервисом `s3` (R2 так и работает).
Зависимостей не добавляем: подпись считается на hashlib/hmac, запросы идут через httpx,
который в студии уже есть.

Ограничения, о которых надо помнить: один PUT — до 5 ГиБ, дальше нужен multipart;
ключ объекта не может быть пустым и не должен начинаться с `/`."""
import hashlib
import hmac
import mimetypes
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx

ALGORITHM = 'AWS4-HMAC-SHA256'
REGION = 'auto'
SERVICE = 's3'
UNSIGNED_PAYLOAD = 'UNSIGNED-PAYLOAD'


class R2Error(RuntimeError):
    """Отказ R2: код, текст и тело ответа."""


def config():
    """Настройки из окружения. Пустая строка означает «не настроено»."""
    return {
        'endpoint': (os.environ.get('R2_ENDPOINT') or '').strip().rstrip('/'),
        'bucket': (os.environ.get('R2_BUCKET') or '').strip(),
        'access_key_id': (os.environ.get('R2_ACCESS_KEY_ID') or '').strip(),
        'secret_access_key': (os.environ.get('R2_SECRET_ACCESS_KEY') or '').strip(),
        'public_base_url': (os.environ.get('R2_PUBLIC_BASE_URL') or '').strip().rstrip('/'),
    }


def enabled(cfg=None):
    cfg = cfg or config()
    return bool(cfg['endpoint'] and cfg['bucket'] and cfg['access_key_id'] and cfg['secret_access_key'])


def readable(cfg=None):
    """Читать можно и без ключей: если у бакета есть публичный домен, объекты видны без подписи."""
    cfg = cfg or config()
    return enabled(cfg) or bool(cfg.get('public_base_url'))


def _sign(key, message):
    return hmac.new(key, message.encode('utf-8'), hashlib.sha256).digest()


def signing_key(secret, date_stamp, region=REGION, service=SERVICE):
    """Ключ подписи: HMAC-цепочка от секрета к дате, региону и сервису."""
    k_date = _sign(('AWS4' + secret).encode('utf-8'), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, 'aws4_request')


def canonical_uri(key):
    """Путь ключа в виде RFC 3986: экранирование сегментов, слэши не трогаем."""
    from urllib.parse import quote
    return '/' + '/'.join(quote(part, safe='') for part in str(key).split('/'))


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def sign_request(method, url, headers, payload_hash, access_key_id, secret_access_key,
                 region=REGION, service=SERVICE, now=None):
    """Подписывает запрос SigV4 и возвращает заголовки с Authorization.

    payload_hash — sha256 тела (или UNSIGNED_PAYLOAD)."""
    now = now or datetime.now(UTC)
    amz_date = now.strftime('%Y%m%dT%H%M%SZ')
    date_stamp = now.strftime('%Y%m%d')
    parsed = httpx.URL(url)
    host = parsed.netloc.decode('ascii') if isinstance(parsed.netloc, bytes) else parsed.netloc

    signed = {'host': host, 'x-amz-date': amz_date}
    for name, value in headers.items():
        signed[name.lower()] = value
    signed_names = sorted(signed)
    canonical_headers = ''.join(f'{name}:{str(signed[name]).strip()}\n' for name in signed_names)
    signed_headers = ';'.join(signed_names)

    # В канон идёт закодированный путь (raw_path), а не декодированный: так же считает botocore.
    raw_path = parsed.raw_path
    encoded_path = raw_path.decode('ascii') if isinstance(raw_path, bytes) else raw_path
    query = parsed.query.decode('ascii') if isinstance(parsed.query, bytes) else parsed.query

    canonical_request = f"{method.upper()}\n{encoded_path}\n{query}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    scope = f'{date_stamp}/{region}/{service}/aws4_request'
    string_to_sign = '\n'.join([ALGORITHM, amz_date, scope, _sha256(canonical_request.encode('utf-8'))])
    signature = hmac.new(signing_key(secret_access_key, date_stamp, region, service),
                          string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    out = dict(headers)
    out['x-amz-date'] = amz_date
    out['x-amz-content-sha256'] = payload_hash
    out['Authorization'] = (f'{ALGORITHM} Credential={access_key_id}/{scope}, '
                             f'SignedHeaders={signed_headers}, Signature={signature}')
    return out


def object_url(cfg, key):
    return f"{cfg['endpoint']}/{cfg['bucket']}{canonical_uri(key)}"


def public_url(cfg, key):
    """Публичная ссылка на объект: домен бакета, если он открыт, иначе S3-адрес."""
    if cfg.get('public_base_url'):
        return f"{cfg['public_base_url']}/{canonical_uri(key).lstrip('/')}"
    return object_url(cfg, key)


def _request(method, cfg, key, *, body=None, headers=None, query='', transport=None, now=None):
    payload = body or b''
    payload_hash = _sha256(payload)
    url = object_url(cfg, key) + (('?' + query) if query else '')
    base_headers = {'content-type': 'application/octet-stream'}
    base_headers.update(headers or {})
    signed = sign_request(method, url, base_headers, payload_hash, cfg['access_key_id'],
                          cfg['secret_access_key'], now=now)
    if transport is not None:
        response = transport(method, url, signed, payload)
    else:
        with httpx.Client(timeout=120) as client:
            response = client.request(method.upper(), url, headers=signed, content=payload or None)
    if response.status_code >= 400:
        raise R2Error(f'R2 ответил {response.status_code}: {getattr(response, "text", "")[:300]}')
    return response


def put_bytes(cfg, key, data, content_type=None, transport=None):
    """Кладёт объект. Возвращает публичную ссылку."""
    content_type = content_type or mimetypes.guess_type(key)[0] or 'application/octet-stream'
    _request('PUT', cfg, key, body=data, headers={'content-type': content_type}, transport=transport)
    return public_url(cfg, key)


def put_file(cfg, path, key=None, content_type=None, transport=None):
    """Кладёт файл с диска. Ключ по умолчанию — путь относительно корня каталога."""
    path = Path(path)
    key = key or path.name
    return put_bytes(cfg, key, path.read_bytes(), content_type or mimetypes.guess_type(str(path))[0],
                     transport=transport)


def head(cfg, key, transport=None):
    """Проверка объекта: есть ли он и какого размера. None — если нет."""
    try:
        response = _request('HEAD', cfg, key, transport=transport)
    except R2Error:
        return None
    return {'size': int(response.headers.get('content-length') or 0),
            'etag': (response.headers.get('etag') or '').strip('"')}


def get_bytes(cfg, key, transport=None):
    response = _request('GET', cfg, key, transport=transport)
    return response.content


def public_get(cfg, key, transport=None):
    """Чтение публичного объекта без ключей.

    S3-API R2 отвечает 400 на неподписанный запрос даже для открытого бакета, поэтому
    публичные объекты читаются через домен бакета (R2_PUBLIC_BASE_URL), а не через S3-эндпоинт."""
    base = (cfg.get('public_base_url') or '').strip().rstrip('/')
    if not base:
        raise R2Error('Нет публичного адреса бакета: задай R2_PUBLIC_BASE_URL или подпиши запрос ключами')
    url = f"{base}/{canonical_uri(key).lstrip('/')}"
    if transport is not None:
        response = transport('GET', url, {}, b'')
    else:
        with httpx.Client(timeout=120) as client:
            response = client.get(url)
    if response.status_code >= 400:
        raise R2Error(f'Публичный объект недоступен: {response.status_code}')
    return response.content


def delete(cfg, key, transport=None):
    _request('DELETE', cfg, key, transport=transport)
    return True
