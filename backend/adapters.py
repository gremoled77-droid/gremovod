"""Адаптеры моделей PiAPI: проверка параметров, тело запроса и оценка цены.

Модуль не делает сетевых вызовов. Канонический формат payload един для всех моделей:
{'model', 'task_type', 'input'}; то, что реально уходит провайдеру, строит wire_body().
Модели с launch_enabled=False доступны только для предпросмотра (/api/model-jobs/preview).
"""
import math
import re
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
        if rule.get('optional') and name not in options:
            continue  # необязательный параметр без значения в запрос не попадает
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


# ---------- Seedance 2.5 (видео, PiAPI: docs/official-prompts/seedance-piapi.txt) ----------
SEEDANCE_TASKS = ('reference', 'edit', 'extend')
SEEDANCE_OPTIONS = {'resolution', 'duration', 'aspect_ratio', 'task', 'draft', 'draft_task_id',
                    'video_seconds', 'audio_seconds'}
SEEDANCE_MAX = {'image': 30, 'video': 10, 'audio': 10}
SEEDANCE_MAX_SECONDS = 30  # суммарно для видео-референсов и для аудио-референсов
TASK_ID = re.compile(r'[A-Za-z0-9_-]{1,100}')


def _seconds(options, name, count):
    """Суммарная длительность референсов задаётся явно: сервис не скачивает файлы и не измеряет их."""
    value = options.get(name)
    if not count:
        if value is not None:
            _bad(f'Параметр {name} нужен только вместе с соответствующими референсами')
        return 0
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= SEEDANCE_MAX_SECONDS:
        _bad(f'Укажи {name}: суммарную длительность референсов в секундах (больше 0 и не более {SEEDANCE_MAX_SECONDS})')
    return value


def _prompt_tags(prompt, images, videos, audios):
    for kind, limit in (('image', images), ('video', videos), ('audio', audios)):
        for index in re.findall(rf'@{kind}(\d+)', prompt, re.IGNORECASE):
            if not 1 <= int(index) <= limit:
                _bad(f'В промпте указан отсутствующий референс @{kind}{index}')


def _build_seedance_final(spec, body, draft):
    """Шаг 2 чернового режима: провайдер берёт промпт, референсы и длительность из черновика."""
    options = body.options
    task_id = options['draft_task_id']
    if not isinstance(task_id, str) or not TASK_ID.fullmatch(task_id):
        _bad('Неверный draft_task_id')
    if options.get('draft'):
        _bad('draft и draft_task_id нельзя использовать вместе')
    if body.reference_urls or body.video_urls or body.audio_urls:
        _bad('В финале по черновику референсы не передаются: они берутся из черновика')
    if set(options) - {'draft_task_id', 'resolution'}:
        _bad('В финале по черновику допустимы только draft_task_id и resolution (1080p)')
    if options.get('resolution', '1080p') != '1080p':
        _bad('Финал по черновику создаётся только в 1080p')
    if not draft:
        _bad('Черновик не найден среди заданий этого проекта или не создан этой моделью в режиме draft')
    return {'model': spec['model'], 'task_type': spec['task_type'],
            'input': {'draft_task_id': task_id, 'resolution': '1080p'},
            'billing': {'resolution': '1080p', 'duration_s': draft['duration_s'], 'video_s': draft['video_s'],
                        'from_draft': True}}


def build_seedance_25(spec, body, draft=None):
    options = body.options
    unknown = set(options) - SEEDANCE_OPTIONS
    if unknown:
        _bad('Неподдерживаемый параметр модели: ' + ', '.join(sorted(unknown)))
    if options.get('draft_task_id'):
        return _build_seedance_final(spec, body, draft)
    images, videos, audios = list(body.reference_urls), list(body.video_urls), list(body.audio_urls)
    check_refs(images, SEEDANCE_MAX['image'])
    check_refs(videos, SEEDANCE_MAX['video'])
    check_refs(audios, SEEDANCE_MAX['audio'])
    _prompt_tags(body.prompt, len(images), len(videos), len(audios))
    video_s = _seconds(options, 'video_seconds', len(videos))
    _seconds(options, 'audio_seconds', len(audios))
    has_refs = bool(images or videos or audios)
    task = options.get('task')
    if task is not None and task not in SEEDANCE_TASKS:
        _bad('Задача task: reference, edit или extend (auto не используется: провайдер определяет тип по промпту)')
    if task is None and has_refs:
        task = 'reference'
    if task and not has_refs:
        _bad('Для задачи нужны референсы')
    if task in ('edit', 'extend') and not videos:
        _bad('Для edit и extend нужен исходный ролик в video_urls')
    resolution = options.get('resolution', '480p')
    if resolution not in spec['resolution']:
        _bad('Недопустимое разрешение: 480p, 720p или 1080p')
    aspect = options.get('aspect_ratio', 'adaptive' if task in ('edit', 'extend') else '16:9')
    if aspect not in spec['aspect_ratio']:
        _bad('Недопустимое соотношение сторон')
    if task in ('edit', 'extend') and aspect != 'adaptive':
        _bad('Для edit и extend допустимо только aspect_ratio adaptive')
    if task == 'edit':
        if 'duration' in options:
            _bad('Для edit длительность не задаётся: результат следует длине исходного ролика')
        if not 4 <= video_s <= SEEDANCE_MAX_SECONDS:
            _bad('Исходный ролик для edit должен быть длиной от 4 до 30 секунд')
        duration, out_s = -1, video_s  # провайдер резервирует длину исходника, лишнее возвращает
    else:
        duration = options.get('duration', 5)
        if type(duration) is not int or not spec['duration_min'] <= duration <= spec['duration_max']:
            _bad(f'Длительность должна быть целым числом от {spec["duration_min"]} до {spec["duration_max"]}')
        out_s = duration
    draft_flag = options.get('draft')
    if draft_flag is not None and draft_flag is not True:
        _bad('draft: только true')
    if draft_flag and resolution != '480p':
        _bad('Черновик создаётся только в 480p')
    inp = {'prompt': body.prompt, 'resolution': resolution, 'duration': duration, 'aspect_ratio': aspect,
           'mode': 'omni_reference' if has_refs else 'text_to_video'}
    if task:
        inp['omni_reference_task_type'] = task
    if images:
        inp[spec['ref_field']] = images
    if videos:
        inp['video_urls'] = videos
    if audios:
        inp['audio_urls'] = audios
    if draft_flag:
        inp['draft'] = True
    return {'model': spec['model'], 'task_type': spec['task_type'], 'input': inp,
            'billing': {'resolution': resolution, 'duration_s': out_s, 'video_s': video_s}}


def cost_seedance_25(spec, payload):
    """Цена выхода плюс половина цены за каждую секунду входных видео-референсов (по документации PiAPI)."""
    billing = payload['billing']
    rate = spec['price_per_second_usd'][billing['resolution']]
    return round(rate * billing['duration_s'] + rate / 2 * billing['video_s'], 3)


def describe_seedance_25(spec, payload):
    """Строки для окна подтверждения (GenerationReview): что именно будет оплачено."""
    billing, inp = payload['billing'], payload['input']
    rate = spec['price_per_second_usd'][billing['resolution']]
    if billing.get('from_draft'):
        lines = [f'Финал 1080p по черновику {inp["draft_task_id"]}: промпт и референсы берутся из черновика.',
                 f'Выход {billing["duration_s"]} с × ${rate}/с']
    else:
        task = inp.get('omni_reference_task_type')
        names = {'reference': 'генерация по референсам', 'edit': 'правка исходного видео (длина по исходнику)',
                 'extend': 'продление исходного видео'}
        lines = []
        if inp.get('draft'):
            lines.append('Черновик 480p: финал 1080p отправляется отдельным подтверждённым запуском.')
        if task:
            lines.append('Задача: ' + names[task])
        counts = [f'{label} {len(inp[key])}' for label, key in (('картинок', 'image_urls'), ('видео', 'video_urls'), ('аудио', 'audio_urls')) if inp.get(key)]
        if counts:
            lines.append('Референсы: ' + ', '.join(counts))
        lines.append(f'Выход {billing["duration_s"]} с × ${rate}/с')
    if billing['video_s']:
        lines.append(f'Входное видео {billing["video_s"]} с × ${round(rate / 2, 4)}/с')
    return lines


# ---------- Image Upscale (PiAPI Qubico/image-toolkit): ПРЕДПРОСМОТР, запуск выключен до живой проверки ----------
def build_image_upscale(spec, body):
    """Один публичный HTTPS-URL, множитель 2 или 4. Размеры входа (in_width/in_height) нужны только для оценки цены."""
    if len(body.reference_urls) != 1:
        _bad('Апскейлу нужна ровно одна картинка-референс')
    check_refs(body.reference_urls, 1)
    options = pick_options(spec, body.options)
    return {'model': spec['model'], 'task_type': spec['task_type'],
            'input': {'image': body.reference_urls[0], 'scale': options['scale']},
            'dims': {'w': options['in_width'], 'h': options['in_height']}}


def cost_image_upscale(spec, payload):
    """$0.001 за мегапиксель результата (1 Мп = 1024²), минимум $0.001. Без размеров входа берётся максимум 2048×2048."""
    scale = payload['input']['scale']
    dims = payload.get('dims') or {'w': spec['max_input_px'], 'h': spec['max_input_px']}
    mpx = dims['w'] * dims['h'] * scale * scale / (1024 * 1024)
    return max(spec['min_price_usd'], round(mpx * spec['price_per_mpx_usd'], 4))


REGISTRY = {
    'image_upscale': (build_image_upscale, cost_image_upscale),
    'unified_image': (build_unified_image, cost_unified_image),
    'gpt_image': (build_gpt_image, cost_gpt_image),
    'minimax_h3': (build_minimax_h3, cost_minimax_h3),
    'seedance_25': (build_seedance_25, cost_seedance_25),
}
DESCRIBE = {'seedance_25': describe_seedance_25}


def handles(spec):
    return spec.get('adapter') in REGISTRY


def build(spec, body, **context):
    """context передаёт адаптеру данные, найденные вызывающим кодом (например draft для финала Seedance)."""
    builder = REGISTRY[spec['adapter']][0]
    return builder(spec, body, **context) if spec['adapter'] == 'seedance_25' else builder(spec, body)


def cost(spec, payload):
    return REGISTRY[spec['adapter']][1](spec, payload)


def describe(spec, payload):
    handler = DESCRIBE.get(spec.get('adapter'))
    return handler(spec, payload) if handler else []


def submit_path(spec):
    return spec.get('submit_path', DEFAULT_SUBMIT_PATH)


def wire_body(spec, payload):
    """Тело HTTP-запроса провайдеру. У GPT Image оно плоское, у остальных — {model, task_type, input}.
    Служебное поле billing (для оценки цены) провайдеру не уходит."""
    if spec.get('adapter') == 'gpt_image':
        return {'model': payload['model'], **payload['input']}
    if spec.get('adapter') == 'image_upscale':  # dims нужны только для оценки цены
        return {k: payload[k] for k in ('model', 'task_type', 'input')}
    return {key: value for key, value in payload.items() if key != 'billing'}
