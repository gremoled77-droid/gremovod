"""HTTP-адаптеры LLM-шлюза: три протокола провайдера, общая форма результата.

Адаптер не выбирает провайдера и не берёт адрес или модель из тела запроса:
адрес, префикс пути и upstream-модель приходят из реестра (backend/llm_gateway.py).
Ключ читается по схеме проекта (backend/connections.py) и в результат не попадает.

До сети стоит гейт владельца: маршрут, который не включён, не подтверждён тарифом
или не разрешён по оптину, сетевого вызова не даёт.

Единственный шов для тестов — внедряемый httpx.AsyncClient: все провайдеры
закрываются httpx.MockTransport, живых сетевых вызовов в тестах нет.

Правило денег: неизвестный исход не равен нулю. Ответ без расхода токенов, таймаут,
отказ провайдера после отправки, 429, 5xx и блокировка Cloudflare помечаются как
«списание возможно» — деньги за них не обнуляются.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx
from fastapi import HTTPException

from backend import connections
from backend import llm_gateway
from backend.llm_gateway import ModelEntry, Registry, Route, Usage

TIMEOUT = 120.0

RESPONSES = 'responses'
ANTHROPIC_MESSAGES = 'anthropic_messages'
OPENAI_CHAT = 'openai_chat'

# Пути протоколов. Префикс пути (path_prefix) приходит из реестра, а не из кода.
PROTOCOL_PATHS = {RESPONSES: '/v1/responses', ANTHROPIC_MESSAGES: '/v1/messages', OPENAI_CHAT: '/v1/chat/completions'}
ANTHROPIC_VERSION = '2023-06-01'
CLOUDFLARE_MARKERS = ('1010', 'browser_signature_banned')


@dataclass(frozen=True)
class ProviderResult:
    """Общая форма ответа провайдера: получился ли ответ, сколько токенов, могло ли уже списаться."""
    ok: bool
    text: str
    usage: Usage
    error_kind: str | None
    charged_possible: bool
    provider_request_id: str | None


def _failure(error_kind: str, *, charged: bool, request_id: str | None = None) -> ProviderResult:
    """Неудачный исход: текста нет, расход неизвестен, тело провайдера наружу не отдаётся."""
    return ProviderResult(ok=False, text='', usage=Usage(None, None, estimated=True),
                           error_kind=error_kind, charged_possible=charged, provider_request_id=request_id)


def _entry_of(route: Route, registry: Registry | None) -> ModelEntry:
    """Запись реестра для маршрута: адрес и upstream-модель берутся только отсюда.

    Провайдер или модель, которых нет в реестре, сетевого вызова не вызывают.
    """
    source = registry if registry is not None else llm_gateway.load_registry()
    entry = source.entry(route.provider, route.model)
    if entry is None:
        raise HTTPException(400, 'Маршрут не найден в реестре: '
                            + str(route.provider) + '/' + str(route.model))
    return entry


def _gate(entry: ModelEntry, *, allow_free: bool) -> None:
    """Гейт владельца до сети: что не включено и не подтверждено — не вызывается.

    Отказ не проходит в провайдера: сети нет, списания нет, журналировать нечего.
    """
    if not entry.enabled:
        raise HTTPException(400, 'Маршрут выключен владельцем: ' + entry.provider + '/' + entry.model)
    if entry.opt_in and not allow_free:
        raise HTTPException(400, 'Маршрут требует явного разрешения владельца: '
                            + entry.provider + '/' + entry.model)
    free_confirmed = entry.free or (entry.input_per_mtok == 0 and entry.output_per_mtok == 0)
    if not free_confirmed and not entry.verified_at:
        raise HTTPException(400, 'Тариф маршрута не подтверждён вживую: ' + entry.provider + '/' + entry.model)


def _endpoint(protocol: str, base_url: str, path_prefix: str = '') -> str:
    """Адрес вызова: база провайдера из реестра, префикс пути из реестра и путь протокола."""
    base = str(base_url or '').strip().rstrip('/')
    if not base.startswith('https://'):
        raise HTTPException(400, 'Адрес провайдера из реестра должен быть HTTPS')
    path = PROTOCOL_PATHS.get(protocol)
    if path is None:
        raise HTTPException(400, 'Протокол провайдера не поддерживается: ' + protocol)
    prefix = str(path_prefix or '').strip().strip('/')
    return base + ('/' + prefix if prefix else '') + path


def _headers(protocol: str, key: str) -> dict:
    """Заголовки вызова. Ключ уходит провайдеру и никуда больше."""
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}
    if protocol == ANTHROPIC_MESSAGES:
        headers['x-api-key'] = key
        headers['anthropic-version'] = ANTHROPIC_VERSION
    return headers


def _body(protocol: str, model_id: str, messages: list[dict], max_tokens: int) -> dict:
    """Тело запроса по протоколу: у каждого свой набор полей."""
    if protocol == RESPONSES:
        return {'model': model_id, 'max_output_tokens': max_tokens,
                'input': [{'role': str(item.get('role') or 'user'), 'content': item.get('content', '')}
                          for item in messages]}
    if protocol == ANTHROPIC_MESSAGES:
        system = '\n'.join(str(item.get('content') or '') for item in messages
                           if str(item.get('role') or '') == 'system')
        chat = [{'role': str(item.get('role') or '') if str(item.get('role') or '') in ('user', 'assistant') else 'user',
                 'content': item.get('content', '')}
                for item in messages if str(item.get('role') or '') != 'system']
        body = {'model': model_id, 'max_tokens': max_tokens, 'messages': chat}
        if system:
            body['system'] = system
        return body
    return {'model': model_id, 'max_tokens': max_tokens,
            'messages': [{'role': str(item.get('role') or 'user'), 'content': item.get('content', '')}
                         for item in messages]}


def _content_text(content) -> str:
    """Текст из строки или из списка частей ответа."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get('text') or ''))
        return ''.join(part for part in parts if part)
    return ''


def _text_of(protocol: str, value: dict) -> str:
    """Текст ответа по форме каждого протокола."""
    if protocol == OPENAI_CHAT:
        for choice in (value.get('choices') or []):
            if not isinstance(choice, dict):
                continue
            message = choice.get('message')
            text = _content_text(message.get('content')) if isinstance(message, dict) else ''
            if text:
                return text
        return ''
    if protocol == ANTHROPIC_MESSAGES:
        parts = [str(block.get('text') or '') for block in (value.get('content') or [])
                 if isinstance(block, dict) and str(block.get('type') or 'text') == 'text']
        return '\n'.join(part for part in parts if part)
    parts = []
    for item in (value.get('output') or []):
        if not isinstance(item, dict) or str(item.get('type') or 'message') != 'message':
            continue
        text = _content_text(item.get('content'))
        if text:
            parts.append(text)
    return '\n'.join(parts)


def _usage_of(protocol: str, value: dict) -> Usage | None:
    """Расход токенов из ответа. Нет usage — расход неизвестен, а не нулевой."""
    usage = value.get('usage')
    if not isinstance(usage, dict):
        return None
    if protocol == OPENAI_CHAT:
        tokens_in = usage.get('prompt_tokens')
        tokens_out = usage.get('completion_tokens')
        cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens')
        reasoning = (usage.get('completion_tokens_details') or {}).get('reasoning_tokens')
    elif protocol == RESPONSES:
        tokens_in = usage.get('input_tokens')
        tokens_out = usage.get('output_tokens')
        cached = (usage.get('input_tokens_details') or {}).get('cached_tokens')
        reasoning = (usage.get('output_tokens_details') or {}).get('reasoning_tokens')
    else:
        tokens_in = usage.get('input_tokens')
        tokens_out = usage.get('output_tokens')
        cached = usage.get('cache_read_input_tokens')
        creation = usage.get('cache_creation_input_tokens')
        reasoning = None
    if tokens_in is None or tokens_out is None:
        return None
    cached = int(cached) if cached is not None else None
    reasoning = int(reasoning) if reasoning is not None else None
    if protocol == ANTHROPIC_MESSAGES:
        # у Anthropic input_tokens не включает кеш: полный вход = input + чтение из кеша + запись в кеш
        tokens_in = int(tokens_in) + (cached or 0) + (int(creation) if creation is not None else 0)
    return Usage(input_tokens=int(tokens_in), output_tokens=int(tokens_out),
                 cached_input_tokens=cached, reasoning_tokens=reasoning, estimated=False)


def _is_error_body(value) -> bool:
    """Тело с ошибкой провайдера при HTTP 200: Kie и провайдеры OpenAI-формы."""
    if not isinstance(value, dict):
        return True
    if isinstance(value.get('error'), (dict, str)):
        return True
    if value.get('success') is False:
        return True
    code = value.get('code')
    if code is not None and str(code) not in ('0', '200'):
        return True
    if str(value.get('status') or '').lower() in ('error', 'failed'):
        return True
    return False


def _request_id(response, value) -> str | None:
    """Идентификатор запроса у провайдера: из тела, иначе из заголовка."""
    if isinstance(value, dict) and value.get('id'):
        return str(value['id'])
    return response.headers.get('x-request-id') or None


def _result_of(protocol: str, response) -> ProviderResult:
    """Ответ провайдера приводится к общей форме: успех, расход токенов или вид сбоя."""
    request_id = response.headers.get('x-request-id') or None
    if response.status_code == 401:
        return _failure('http_401', charged=False, request_id=request_id)
    if response.status_code == 403:
        if any(marker in response.text for marker in CLOUDFLARE_MARKERS):
            return _failure('cloudflare_1010', charged=True, request_id=request_id)
        return _failure('http_403', charged=True, request_id=request_id)
    if response.status_code == 429:
        return _failure('http_429', charged=True, request_id=request_id)
    if response.status_code >= 500:
        return _failure('http_5xx', charged=True, request_id=request_id)
    if response.status_code >= 400:
        # провайдер отклонил запрос: обработки не было, списания не было
        return _failure('bad_body', charged=False, request_id=request_id)
    try:
        value = response.json()
    except ValueError:
        # нечитаемое тело: неизвестно, успел ли провайдер обработать запрос
        return _failure('bad_body', charged=True, request_id=request_id)
    request_id = _request_id(response, value)
    if _is_error_body(value):
        return _failure('bad_body', charged=False, request_id=request_id)
    usage = _usage_of(protocol, value)
    if usage is None:
        return _failure('no_usage', charged=True, request_id=request_id)
    text = _text_of(protocol, value)
    if not text:
        return _failure('bad_body', charged=True, request_id=request_id)
    return ProviderResult(ok=True, text=text, usage=usage, error_kind=None,
                          charged_possible=False, provider_request_id=request_id)


async def complete(route: Route, messages: list[dict], max_tokens: int, *,
                    client: httpx.AsyncClient | None = None,
                    api_key: str | None = None,
                    registry: Registry | None = None,
                    allow_free: bool = False) -> ProviderResult:
    """Вызов провайдера по маршруту. Тело ответа приводится к общей форме результата.

    registry — реестр шлюза; не передан — читается из файла конфигурации.
    api_key — ключ, полученный запросом; не передан — берётся по схеме backend/connections.py.
    allow_free — разрешение владельца на бесплатные по оптину маршруты.
    """
    entry = _entry_of(route, registry)
    _gate(entry, allow_free=allow_free)
    protocol = str(entry.protocol or '')
    if protocol not in (RESPONSES, ANTHROPIC_MESSAGES, OPENAI_CHAT):
        raise HTTPException(400, 'Протокол провайдера не поддерживается: ' + protocol)
    if not isinstance(messages, list) or not messages:
        raise HTTPException(400, 'Ожидался список сообщений')
    if not isinstance(max_tokens, int) or max_tokens <= 0:
        raise HTTPException(400, 'Ожидалось положительное число токенов ответа')
    key = (api_key or '').strip() or connections.provider_key(entry.provider)
    url = _endpoint(protocol, entry.base_url, entry.path_prefix)
    body = _body(protocol, entry.model_id, messages, max_tokens)
    headers = _headers(protocol, key)
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=TIMEOUT) as own:
                response = await own.post(url, headers=headers, json=body)
        else:
            response = await client.post(url, headers=headers, json=body)
    except httpx.ConnectError:
        # соединение не установлено: запрос провайдеру не дошёл
        return _failure('timeout', charged=False)
    except httpx.TimeoutException:
        # запрос ушёл, ответа нет: списание могло произойти
        return _failure('timeout', charged=True)
    except httpx.RequestError:
        return _failure('timeout', charged=True)
    return _result_of(protocol, response)
