"""Адаптеры моделей PiAPI: проверка параметров, тело запроса и оценка цены.

Модуль не делает сетевых вызовов. Канонический формат payload един для всех моделей:
{'model', 'task_type', 'input'}; то, что реально уходит провайдеру, строит wire_body().
Модели с launch_enabled=False доступны только для предпросмотра (/api/model-jobs/preview).
"""
from urllib.parse import urlsplit

from fastapi import HTTPException

DEFAULT_SUBMIT_PATH = '/api/v1/task'


def _bad(message):
    raise HTTPException(400, message)


def check_refs(urls, limit):
    if limit == 0 and urls:
        _bad('Эта модель не принимает референсы')
    if len(urls) > limit:
        _bad(f'Превышено число референсов: максимум {limit}')
    for ref in urls:
        parsed = urlsplit(ref)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.hostname in {'localhost', '127.0.0.1', '::1'}):
            _bad('Нужен публичный HTTPS URL референса; локальный файл нельзя передать провайдеру напрямую')


def pick_options(spec, options):
    """Применить схему параметров модели: значения по умолчанию, перечисления, целые диапазоны."""
    schema = spec['options']
    unknown = set(options) - set(schema)
    if unknown:
        _bad('Неподдерживаемый параметр модели: ' + ', '.join(sorted(unknown)))
    result = {}
    for name, rule in schema.items():
        value = options.get(name, rule.get('default'))
        if 'values' in rule:
            if value not in rule['values']:
                _bad(f'Недопустимое значение параметра {name}')
        elif type(value) is not int or not rule['min'] <= value <= rule['max']:
            _bad(f'Параметр {name} должен быть целым числом от {rule["min"]} до {rule["max"]}')
        result[name] = value
    return result


# ---------- unified image (Seedream Pro, Nano Banana 2.1, Qwen Image 2.1) ----------
def build_unified_image(spec, body):
    check_refs(body.reference_urls, spec.get('api_refs', 0))
    options = pick_options(spec, body.options)
    if spec.get('max_pixels') and options.get('width', 0) * options.get('height', 0) > spec['max_pixels']:
        _bad('Произведение ширины и высоты превышает лимит модели')
    payload = {'model': spec['model'], 'task_type': spec['task_type'],
               'input': {'prompt': body.prompt, **options}}
    if body.reference_urls:
        payload['input'][spec['ref_field']] = list(body.reference_urls)
    return payload


def cost_unified_image(spec, payload):
    inp = payload['input']
    table = spec.get('price_by_size')
    if table:
        price = table[inp.get('size') or inp.get('resolution')]
        extra = max(0, len(inp.get(spec.get('ref_field', ''), [])) - 1)
        return round(price + extra * spec.get('extra_ref_usd', 0), 4)
    return spec['price_usd']


# ---------- GPT Image (async-эндпоинты PiAPI) ----------
def build_gpt_image(spec, body):
    if body.reference_urls:
        _bad('Правки и референсы GPT Image подключаются после проверки эндпоинта edits '
             '(для правок планируется gpt-image-2.5-sunburst)')
    options = pick_options(spec, body.options)
    variants = spec.get('variants')
    model = variants[options['variant']] if variants else spec['model']
    inp = {'prompt': body.prompt, 'n': 1, 'response_format': 'url', 'output_format': 'png'}
    if model != 'gpt-image-2.5':  # без суффикса модель сама выбирает размер и качество
        inp['size'] = options['size']
        inp['quality'] = options['quality']
    return {'model': model, 'task_type': 'gpt-image-generation', 'input': inp}


def cost_gpt_image(spec, payload):
    inp = payload['input']
    model = payload['model']
    if model == 'gpt-image-2.5':
        return spec['price_standard_max_usd']
    price = spec['price_by_quality'][model][inp['quality']]
    return round(price * (1 if inp['size'] == '1024x1024' else 1.5), 4)


# ---------- MiniMax H3 (видео) ----------
def build_minimax_h3(spec, body):
    check_refs(body.reference_urls, 1)
    if len(body.prompt) > 2000:
        _bad('Промпт MiniMax H3 — не более 2000 символов')
    options = pick_options(spec, body.options)
    inp = {'prompt': body.prompt, **options}
    task_type = 'txt2video'
    if body.reference_urls:
        task_type = 'img2video'
        inp['image'] = body.reference_urls[0]
    return {'model': spec['model'], 'task_type': task_type, 'input': inp}


def cost_minimax_h3(spec, payload):
    inp = payload['input']
    return round(spec['price_per_second_usd'][inp['resolution']] * inp['duration'], 3)


REGISTRY = {
    'unified_image': (build_unified_image, cost_unified_image),
    'gpt_image': (build_gpt_image, cost_gpt_image),
    'minimax_h3': (build_minimax_h3, cost_minimax_h3),
}


def handles(spec):
    return spec.get('adapter') in REGISTRY


def build(spec, body):
    return REGISTRY[spec['adapter']][0](spec, body)


def cost(spec, payload):
    return REGISTRY[spec['adapter']][1](spec, payload)


def submit_path(spec):
    return spec.get('submit_path', DEFAULT_SUBMIT_PATH)


def wire_body(spec, payload):
    """Тело HTTP-запроса провайдеру. У GPT Image оно плоское, у остальных — {model, task_type, input}."""
    if spec.get('adapter') == 'gpt_image':
        return {'model': payload['model'], **payload['input']}
    return payload
