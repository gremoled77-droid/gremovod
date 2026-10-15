"""Каталог моделей и допустимых LLM. Вынесено из main.py без изменения содержимого."""

ALLOWED_CHAT={'gpt-5.6-luna','gpt-5.6-terra','gpt-5.6-sol'}
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
