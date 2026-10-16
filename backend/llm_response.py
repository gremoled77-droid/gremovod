"""Разбор ответа LLM от PiAPI (/v1/chat/completions) для разных моделей, включая GPT-6 Astra."""
from fastapi import HTTPException


def _part_text(part):
    if isinstance(part, str):
        return part
    if isinstance(part, dict):
        text = part.get('text')
        if isinstance(text, dict):  # {'text': {'value': '...'}}
            text = text.get('value')
        return text if isinstance(text, str) else ''
    return ''


def upstream_error(value):
    """Читаемое сообщение, если PiAPI вернул ошибку в теле ответа (даже при HTTP 200)."""
    if not isinstance(value, dict):
        return ''
    error = value.get('error')
    if isinstance(error, dict):
        error = error.get('message') or error.get('code')
    if not error and 'choices' not in value and value.get('code', 200) not in (0, 200):
        error = value.get('message') or value.get('msg') or f"код {value.get('code')}"
    return str(error)[:300] if error else ''


def chat_text(value):
    """Достаёт текст ответа: content может быть строкой или списком частей; пустой ответ — понятная ошибка."""
    problem = upstream_error(value)
    if problem:
        raise HTTPException(502, f'PiAPI вернул ошибку модели: {problem}')
    choices = value.get('choices') if isinstance(value, dict) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise HTTPException(502, 'PiAPI вернул ответ без поля choices; проверь название модели и формат запроса')
    choice = choices[0]
    message = choice.get('message') if isinstance(choice.get('message'), dict) else {}
    content = message.get('content')
    if isinstance(content, list):
        text = ''.join(_part_text(p) for p in content)
    else:
        text = content if isinstance(content, str) else ''
    if not text.strip():
        text = message.get('refusal') if isinstance(message.get('refusal'), str) else ''
    if not text.strip():
        reason = choice.get('finish_reason') or 'неизвестно'
        hint = ' Модель потратила лимит токенов на размышления: увеличь max_tokens.' if reason == 'length' else ''
        raise HTTPException(502, f'Модель вернула пустой ответ (finish_reason: {reason}).{hint}')
    return text.strip()
