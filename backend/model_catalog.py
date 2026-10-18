"""Каталог моделей и допустимых LLM. Вынесено из main.py без изменения содержимого."""

# gpt-6-astra дорогая: только для сценария и промптов (Идея, Настройки), пока не появится GPT-6.1 Sol. В узлах Воркфлоу её нет.
ALLOWED_CHAT={'gpt-5.6-luna','gpt-5.6-terra','gpt-5.6-sol','gpt-6-astra'}
IMAGE_TASKS={'seedream-5-pro','seedream-5-lite','gpt-image-2','nano-banana-2','qwen-image-2.1'}
VIDEO_MODELS={'seedance','kling','wan','veo','sora','hailuo'}

# Prototype model catalog. Only launch_enabled adapters have a checked launch schema and price.
MODEL_SPECS = {
 'hunyuan-i2v': {'launch_enabled':True,'verified_at':'2026-10-15','price_usd':0.09,'adapter':'hunyuan_i2v','kind':'video','model':'Qubico/hunyuan','task_type':'img2video-replace','max_refs':1,'ref_field':'image','docs':'https://piapi.ai/docs/hunyuan-video/txt2video-api','duration_mode':'provider_default'},
 'seedream-5-pro': {'launch_enabled':False,'kind':'image','model':'seedream','task_type':'seedream-5-pro','size':['1K','2K'],'aspect_ratio':['16:9','9:16','1:1','4:3','3:4','3:2','2:3','4:5','5:4','21:9'],'output_format':['png','jpeg','webp'],'max_refs':10,'ref_field':'image_urls','docs':'https://app.piapi.ai/docs/seedream-api/seedream-5'},
 'seedream-5-lite': {'launch_enabled':True,'verified_at':'2026-10-15','price_usd':0.052,'kind':'image','model':'seedream','task_type':'seedream-5-lite','size':['2K','3K'],'aspect_ratio':['16:9','9:16','1:1','4:3','3:4','3:2','2:3','4:5','5:4','21:9'],'output_format':['png','jpeg','webp'],'max_refs':10,'ref_field':'image_urls','docs':'https://app.piapi.ai/docs/seedream-api/seedream-5'},
 'nano-banana-2.1': {'launch_enabled':False,'kind':'image','model':'gemini','task_type':'nano-banana-2.1','resolution':['1K','2K','4K'],'aspect_ratio':['16:9','9:16','1:1','4:3','3:4'],'output_format':['png','jpg','webp'],'max_refs':10,'ref_field':'image_urls','docs':'https://piapi.ai/docs/gemini-api/nano-banana-2'},
 'seedance-2.5': {'launch_enabled':True,'verified_at':'2026-10-15','price_per_second_usd':{'480p':0.15,'720p':0.35,'1080p':0.8},'kind':'video','model':'seedance','task_type':'seedance-2.5','resolution':['480p','720p','1080p'],'aspect_ratio':['16:9','9:16','4:3','3:4','21:9','1:1','adaptive'],'duration_min':4,'duration_max':30,'max_refs':30,'ref_field':'image_urls','docs':'https://piapi.ai/docs/seedance-api/seedance-25'}
}

# Prompt-only profiles do not enable or invent a paid provider schema.
for _id, _kind, _docs in [
    ('gpt-image-2','image','https://developers.openai.com/api/docs/guides/image-prompting'),
    ('gpt-image-2.5','image','https://developers.openai.com/api/docs/guides/image-prompting'),
    ('qwen-image-2.1','image','https://www.alibabacloud.com/help/en/model-studio/qwen-image-edit-guide'),
    ('qwen-image-3.0','image','https://www.alibabacloud.com/help/en/model-studio/qwen-image-edit-guide'),
    ('wan-3.0','video','https://www.alibabacloud.com/help/en/model-studio/wan3-video-generation-prompt-guide'),
    ('ltx-2.5','video','https://docs.ltx.io/open-source-model/usage-guides/prompting-guide/'),
    ('kling-3.0','video','https://kling.ai/quickstart/klingai-video-3-model-user-guide')]:
    MODEL_SPECS[_id]={'launch_enabled':False,'kind':_kind,'model':_id,'task_type':_id,
                      'max_refs':10,'docs':_docs,'prompt_only':True}


# --- Адаптеры (16.10.2026). launch_enabled=False: только предпросмотр, пока параметры и цена
# --- не проверены реальным вызовом (см. TODO.md и docs/PIAPI_MODELS_2026-10-16.md).
_ASPECT=['16:9','9:16','1:1','4:3','3:4','3:2','2:3','4:5','5:4','21:9']
MODEL_SPECS['seedream-5-pro'].update({
    'adapter':'unified_image','api_refs':10,'ref_field':'image_urls',
    'price_by_size':{'1K':0.068,'2K':0.136},'extra_ref_usd':0.006,
    'options':{'size':{'values':['1K','2K'],'default':'1K'},
               'aspect_ratio':{'values':_ASPECT,'default':'1:1'},
               'output_format':{'values':['png','jpeg','webp'],'default':'png'}}})
MODEL_SPECS['nano-banana-2.1'].update({
    'adapter':'unified_image','api_refs':10,'ref_field':'image_urls',
    'price_by_size':{'1K':0.03,'2K':0.04,'4K':0.09},
    'options':{'resolution':{'values':['1K','2K','4K'],'default':'1K'},
               'aspect_ratio':{'values':['16:9','9:16','1:1','4:3','3:4'],'default':'16:9'},
               'output_format':{'values':['png','jpg','webp'],'default':'png'}}})
MODEL_SPECS['qwen-image-2.1'].update({
    'adapter':'unified_image','model':'Qubico/qwen-image-2.1','task_type':'txt2img','api_refs':0,
    'price_usd':0.015,'max_pixels':1763584,
    'options':{'width':{'min':64,'max':4096,'default':1024},'height':{'min':64,'max':4096,'default':1024},
               'steps':{'min':1,'max':16,'default':8},'seed':{'min':-1,'max':2147483647,'default':-1}}})
_GPT_COMMON={'adapter':'gpt_image','submit_path':'/api/v1/images/generations/async',
             'price_by_quality':{'gpt-image-2':{'medium':0.032},
                                 'gpt-image-2.5-flare':{'low':0.004,'medium':0.010,'high':0.040},
                                 'gpt-image-2.5-sunburst':{'low':0.004,'medium':0.010,'high':0.040}}}
MODEL_SPECS['gpt-image-2'].update({**_GPT_COMMON,'options':{
    'size':{'values':['1024x1024','1024x1536','1536x1024'],'default':'1024x1024'},
    'quality':{'values':['medium'],'default':'medium'}}})
MODEL_SPECS['gpt-image-2.5'].update({**_GPT_COMMON,'price_standard_max_usd':0.012,
    'variants':{'flare':'gpt-image-2.5-flare','standard':'gpt-image-2.5','sunburst':'gpt-image-2.5-sunburst'},
    'edit_variant':'sunburst','options':{
    'variant':{'values':['flare','standard','sunburst'],'default':'flare'},
    'size':{'values':['1024x1024','1024x1536','1536x1024'],'default':'1024x1024'},
    'quality':{'values':['low','medium','high'],'default':'medium'}}})
MODEL_SPECS['minimax-h3']={
    'launch_enabled':False,'kind':'video','model':'Qubico/minimax-h3','task_type':'txt2video','adapter':'minimax_h3',
    'max_refs':1,'ref_field':'image','docs':'https://piapi.ai/minimax-h3',
    'price_per_second_usd':{'480p':0.03,'768p':0.05,'1080p':0.07},
    'options':{'resolution':{'values':['480p','768p','1080p'],'default':'480p'},
               'duration':{'min':5,'max':15,'default':5},
               'aspect_ratio':{'values':['16:9','9:16','1:1'],'default':'16:9'},
               # seed: по документации PiAPI необязательное целое «для воспроизводимости»; диапазон в доках не указан, не проверялся вживую.
               'seed':{'min':0,'max':2147483647,'optional':True}}}


# Seedance 2.5: адаптер сам валидирует картинки, видео, аудио, edit/extend и draft (backend/adapters.py).
MODEL_SPECS['seedance-2.5']['adapter']='seedance_25'


# --- Живая проверка 16.10.2026 (scripts/live_piapi_test.py): отправка, статус, результат и списание совпали с оценкой.
# gpt-image-2.5-sunburst (правки) и референсы GPT Image не проверялись и остаются выключенными.
for _id in ('seedream-5-pro','nano-banana-2.1','qwen-image-2.1','gpt-image-2','gpt-image-2.5','minimax-h3'):
    MODEL_SPECS[_id].update({'launch_enabled':True,'verified_at':'2026-10-16','prompt_only':False})

# --- Апскейл изображений PiAPI (docs: piapi.ai/docs/image-editing-api/super-resolution-api, прочитано 16.10.2026).
# Параметры и цена взяты из документации, живой вызов НЕ делался: launch_enabled=False, только предпросмотр.
# Расхождение в доках: пример ответа показывает data.output, схема описывает data.task_result.task_output.image_url.
MODEL_SPECS['image-upscale']={
    'launch_enabled':False,'kind':'image','tool':True,'adapter':'image_upscale','prompt_only':False,
    'model':'Qubico/image-toolkit','task_type':'upscale','max_refs':1,'api_refs':1,'ref_field':'image',
    'price_per_mpx_usd':0.001,'min_price_usd':0.001,'max_input_px':2048,
    'options':{'scale':{'values':[2,4],'default':2},
               'in_width':{'min':1,'max':2048,'default':2048},
               'in_height':{'min':1,'max':2048,'default':2048}},
    'docs':'https://piapi.ai/docs/image-editing-api/super-resolution-api'}



# --- Референсы и синтаксис тегов видеомоделей (16.10.2026). Справочные поля из инструкций владельца
# --- и практикума GORA ACADEMY (см. skills/video-*): API они не вызывают и launch_enabled/цены не меняют.
# --- Лимиты провайдера (PiAPI) могут отличаться, не проверено вживую. None = лимит в инструкции не указан.
_REF_PROFILES = {
    'seedance-2.0': {
        'ref_limits': {'image':9,'video':3,'audio':3,'total':15,'video_total_s':15.4,'audio_total_s':15,
                       'duration_min_s':4,'duration_max_s':15,
                       'note':'по документации PiAPI (17.10.2026); аудио одно не принимается, нужен ещё образ или видео'},
        'ref_syntax': {'style':'at_numbered','image':'@image{n}','video':'@video{n}','audio':'@audio{n}',
                       'piapi':{'model':'seedance','task_types':['seedance-2','seedance-2-fast','seedance-2-mini'],
                                'less_restriction_suffix':'-less-restriction','modes':['text_to_video','first_last_frames','omni_reference'],
                                'asset':'asset://{asset_id}','asset_only_on':'less-restriction'},
                       'rule':'каждому тегу одна роль в первой строке промпта; asset:// только у -less-restriction'}},
    'seedance-2.5': {
        'ref_limits': {'image':30,'video':10,'audio':10,'total':50,'video_total_s':30,'audio_total_s':30,
                       'duration_min_s':4,'duration_max_s':30,
                       'note':'по документации PiAPI; адаптер студии отправляет картинки, видео, аудио, edit/extend и draft (не проверено вживую)'},
        'ref_syntax': {'style':'at_numbered','image':'@image{n}','video':'@video{n}','audio':'@audio{n}',
                       'rule':'строчные теги по порядку массивов; ссылка на отсутствующий файл даёт 400',
                       'tasks':['auto','reference','edit','extend'],'draft_mode':True}},
    'flux-3': {
        'ref_limits': {'image':None,'video':1,'audio':0,'total':None,
                       'note':'мультиреференса нет (Omni Reference: Soon); картинки только как старт-кадр или Keyframes по порядку'},
        'ref_syntax': {'style':'none','modes':['t2v','i2v','keyframes','video_continuation'],
                       'rule':'порядок загрузки = порядок кадров; идентичность держит дословное описание субъекта (CASTLE)'}},
    'minimax-h3': {
        'ref_limits': {'image':9,'video':3,'audio':3,'total':12,'video_total_s':15,'audio_total_s':15,
                       'duration_min_s':4,'duration_max_s':15,
                       'note':'Omni Reference из инструкции владельца (приложение Hailuo); через PiAPI только txt2video и img2video с одним первым кадром (max_refs)'},
        'ref_syntax': {'style':'words_numbered','image':'Image {n}','video':'Video {n}','audio':'Audio {n}',
                       'piapi':{'modes':['txt2video','img2video'],'first_frame_only':True,'resolution_case':'lower'},
                       'rule':'назначать роль, не описывать содержимое; после имени обращаться по имени; в API теги не отправляются'}},
    'kling-3.0-omni': {
        'ref_limits': {'image':7,'image_with_video':4,'video':1,'audio':0,'elements':3,'images_per_element':4,
                       'video_max_s':10,'element_video_s':[3,8],'voice_s':[3,30],
                       'duration_min_s':3,'duration_max_s':15,'shots_max':6,'prompt_chars':2500,
                       'note':'лимиты у провайдеров отличаются; голос задаётся элементом, не отдельным аудио'},
        'ref_syntax': {'style':'at_name','element':'@{name}','alternatives':['<<<element_{n}>>>','<<<image_{n}>>>','<<<video_{n}>>>','<<<voice_{n}>>>','@Image{n}'],
                       'piapi':{'model':'kling','task_type':'omni_video_generation','image':'@image_{n}','video':'@video',
                                'fields':['prompt','version','resolution','duration','aspect_ratio','enable_audio','multi_shots','video','images','keep_original_audio'],
                                'elements_and_voice':False},
                       'provider_dependent':True,'rule':'через PiAPI теги @image_N и @video; @имя и <<<element_n>>> относятся к интерфейсу kling.ai'}},
    'kling-3.0': {
        'ref_limits': {'image':2,'first_last':True,'multishot_with_last_frame':False,'images_per_element':3,
                       'duration_min_s':3,'duration_max_s':15,'shots_max':6,'prompt_chars':2500,
                       'note':'режим Start+Last Frame; в мультишоте доступен только первый кадр'},
        'ref_syntax': {'style':'positional','fields':['image_url','image_tail_url'],'alt':'у других провайдеров image/image_tail или frame: first|last',
                       'piapi':{'model':'kling','task_type':'video_generation','versions':['3.0','3.0-turbo'],
                                'fields':['prompt','version','mode','image_url','image_tail_url','duration','aspect_ratio','enable_audio','prefer_multi_shots','multi_shots'],
                                'turbo_audio':False,'turbo_multishot':False},
                       'provider_dependent':True,'rule':'ласт-кадр делать из старт-кадра; промпт описывает только переход'}},
}
for _id, _profile in _REF_PROFILES.items():
    if _id not in MODEL_SPECS:
        _limits = _profile['ref_limits']
        MODEL_SPECS[_id] = {'launch_enabled':False,'kind':'video','model':_id,'task_type':_id,
                            'max_refs':_limits.get('image') or 1,'docs':'skills/video-'+_id.replace('.', '-')+'/SKILL.md',
                            'prompt_only':True}
    MODEL_SPECS[_id].update(_profile)


# --- Seedream 5 Lite: параметры и цена по размеру (раньше шёл по старому пути без схемы параметров).
# --- Цены по таблице PiAPI (17.10.2026, вставлена владельцем): lite 2K/3K $0.052, pro 1K $0.068, 2K $0.136.
MODEL_SPECS['seedream-5-lite'].update({
    'adapter':'unified_image','api_refs':10,'ref_field':'image_urls',
    'price_by_size':{'2K':0.052,'3K':0.052},
    'options':{'size':{'values':['2K','3K'],'default':'2K'},
               'aspect_ratio':{'values':_ASPECT,'default':'1:1'},
               'output_format':{'values':['png','jpeg','webp'],'default':'png'}}})

# Варианты less-restriction: цены из той же таблицы PiAPI; task_type = имя модели из таблицы. Живой проверки не было,
# поэтому запуск выключен (только предпросмотр и цена), пока владелец не разрешит пробный вызов.
for _base, _prices in (('seedream-5-lite', {'2K':0.065,'3K':0.065}), ('seedream-5-pro', {'1K':0.085,'2K':0.17})):
    _spec = {k: v for k, v in MODEL_SPECS[_base].items() if k not in ('verified_at', 'price_usd')}
    _spec.update({'launch_enabled':False,'prompt_only':False,'task_type':_base+'-less-restriction',
                  'price_by_size':_prices,'family':_base})
    MODEL_SPECS[_base+'-less-restriction'] = _spec


# --- KIE (второй провайдер, 18.10.2026). Схемы: model-studio/seedream-schema.json и qwen-schema.json (каталог KIE 15.10.2026).
# --- Цены со страниц kie.ai/seedream-5-pro и kie.ai/qwen-image-2.1 (18.10.2026): 1 кредит = $0.005.
# --- Обе модели image-to-image: нужен хотя бы один публичный референс.
_KIE_COMMON={'launch_enabled':False,'prompt_only':False,'provider':'kie','kind':'image','adapter':'kie_image',
             'task_type':'image-to-image','submit_path':'/api/v1/jobs/createTask','max_refs':10,'api_refs':10,'ref_field':'image_urls'}
MODEL_SPECS['kie-seedream-5-pro']={**_KIE_COMMON,'model':'seedream/5-pro-image-to-image',
    'tier_field':'quality','price_by_tier':{'basic':0.035,'high':0.07},'extra_ref_usd':0.0025,
    'fixed_input':{'nsfw_checker':True},
    'options':{'quality':{'values':['basic','high'],'default':'basic'},  # basic = 1K, high = 2K
               'aspect_ratio':{'values':['16:9','9:16','1:1','4:3','3:4','3:2','2:3','21:9'],'default':'16:9'},
               'output_format':{'values':['png','jpeg'],'default':'png'}},
    'docs':'https://kie.ai/seedream-5-pro'}
MODEL_SPECS['kie-qwen-image-2.1']={**_KIE_COMMON,'model':'qwen2-1/image-to-image',
    'tier_field':'resolution','price_by_tier':{'1K':0.02,'2K':0.04},
    'fixed_input':{'nsfw_checker':True,'enhance_prompt':False},  # промпт пишет студия, без переписывания у провайдера
    'options':{'resolution':{'values':['1K','2K'],'default':'1K'},
               'aspect_ratio':{'values':['auto','16:9','9:16','1:1','4:3','3:4','3:2','2:3','21:9','9:21'],'default':'auto'},
               'output_format':{'values':['png','webp','jpeg'],'default':'png'}},
    'docs':'https://kie.ai/qwen-image-2.1'}
# Живая проверка 18.10.2026 (разрешил владелец): по одному запуску с одним референсом, 16:9.
# Seedream basic: 7 кредитов, 134 с, PNG 1376×768; Qwen 1K: 4 кредита, 29 с, PNG 1376×768. Списание = оценка ($0.055).
# Режимы high и 2K не запускались: до своей проверки они убраны из параметров, цены оставлены в таблице.
for _id, _tier in (('kie-seedream-5-pro', 'quality'), ('kie-qwen-image-2.1', 'resolution')):
    _rule = MODEL_SPECS[_id]['options'][_tier]
    _rule['values'] = [_rule['default']]
    MODEL_SPECS[_id].update({'launch_enabled':True,'verified_at':'2026-10-18'})


# --- Страница модели у провайдера (кнопка «i» в «Кадрах»). Интерфейс берёт ссылку из page_urls[provider],
# --- поэтому при втором API-сервисе достаточно добавить его ключ и ссылки; код экрана не меняется.
# --- Ссылки на страницы моделей владелец даст позже: пока берём только адреса docs на домене провайдера.
PROVIDER_HOSTS = {'piapi': 'piapi.ai', 'kie': 'kie.ai'}
_GPT_PAGE = 'https://piapi.ai/docs/gpt-image/gpt-image-api'
PAGE_URLS = {  # {model_id: {provider: url}}: явные ссылки имеют приоритет над docs
    'gpt-image-2': {'piapi': _GPT_PAGE},
    'gpt-image-2.5': {'piapi': _GPT_PAGE},  # страница API GPT Image (даёт владелец, 17.10.2026)
    # Страница Qwen Image 2.1 у PiAPI не найдена: общая страница qwen-image (про 2.1 на ней не сказано).
    'qwen-image-2.1': {'piapi': 'https://piapi.ai/qwen-image'},
}
for _id, _spec in MODEL_SPECS.items():
    _spec.setdefault('provider', 'piapi')
    _urls = dict(PAGE_URLS.get(_id, {}))
    _docs = str(_spec.get('docs') or '')
    for _name, _host in PROVIDER_HOSTS.items():
        _parts = _docs.split('/')
        if _name not in _urls and _docs.startswith('https://') and len(_parts) > 2 and _parts[2].endswith(_host):
            _urls[_name] = _docs
    _spec['page_urls'] = _urls
