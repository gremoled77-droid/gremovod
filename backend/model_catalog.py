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
               'aspect_ratio':{'values':['16:9','9:16','1:1'],'default':'16:9'}}}


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
