"""Download a fixed set of official prompt sources, retaining provenance and failures."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse
import hashlib,json,httpx

ROOT=Path(__file__).resolve().parents[1]/'docs'/'official-prompts'
SOURCES=[
 ('openai-image-prompting','OpenAI','https://developers.openai.com/api/docs/guides/image-prompting.md'),
 ('openai-image-api','OpenAI','https://developers.openai.com/api/docs/guides/image-generation.md'),
 ('openai-pricing','OpenAI','https://developers.openai.com/api/docs/pricing.md'),
 ('seedance-piapi','PiAPI','https://piapi.ai/docs/seedance-api/seedance-25'),
 ('seedance2-piapi','PiAPI','https://piapi.ai/docs/seedance-api/seedance-2'),
 ('seedance-private-asset-piapi','PiAPI','https://piapi.ai/docs/seedance-api/private-asset'),
 ('kling3-piapi','PiAPI','https://piapi.ai/docs/kling-api/kling-3-api'),
 ('kling3-omni-piapi','PiAPI','https://piapi.ai/docs/kling-api/kling-3-omni-api'),
 ('wan3-prompting','Alibaba Cloud','https://www.alibabacloud.com/help/en/model-studio/wan3-video-generation-prompt-guide'),
 ('ltx25-prompting','Lightricks','https://docs.ltx.io/open-source-model/usage-guides/prompting-guide/'),
 ('kling3-guide','Kling AI','https://kling.ai/quickstart/klingai-video-3-model-user-guide'),
 ('kling3-omni-guide','Kling AI','https://kling.ai/quickstart/klingai-video-3-omni-model-user-guide'),
 ('seedream5-guide','ByteDance Volcengine','https://docs.volcengine.com/docs/ark/seedream-4-0-5-0-prompt-guide?lang=zh'),
 ('seedream5-api','BytePlus','https://docs.byteplus.com/en/docs/ModelArk/image-generation-api'),
 ('seedream5-pro','BytePlus','https://docs.byteplus.com/zh-TW/docs/modelark/seedream-5-0-pro?redirect=1'),
 ('seedream5-piapi','PiAPI','https://app.piapi.ai/docs/seedream-api/seedream-5'),
 ('banana21-model','Google','https://ai.google.dev/gemini-api/docs/models/gemini-nano-banana-2.1?hl=en'),
 ('banana-prompting','Google','https://ai.google.dev/gemini-api/docs/image-generation'),
 ('banana-framework','Google Cloud','https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana'),
 ('qwen21-model','Qwen','https://qwen.ai/blog?id=qwen-image-2.1'),
 ('qwen3-model','Qwen','https://qwen.ai/blog?id=qwen-image-3.0'),
 ('qwen-edit-guide','Alibaba Cloud','https://www.alibabacloud.com/help/en/model-studio/qwen-image-edit-guide'),
]

class ExtractText(HTMLParser):
    def __init__(self): super().__init__();self.skip=0;self.text=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','noscript'}: self.skip+=1
        if tag=='a':
            href=dict(attrs).get('href','')
            if href:self.links.append(href)
    def handle_endtag(self,tag):
        if tag in {'script','style','noscript'}: self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip and data.strip():self.text.append(data.strip())

def fetch(source):
    sid,publisher,url=source
    item={'id':sid,'publisher':publisher,'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat()}
    try:
        response=httpx.get(url,timeout=40,follow_redirects=True)
        item.update(http_status=response.status_code,final_url=str(response.url))
        response.raise_for_status()
        raw=response.content
        extension='.html' if 'html' in response.headers.get('content-type','') else '.md'
        (ROOT/(sid+extension)).write_bytes(raw)
        parser=ExtractText()
        if extension=='.html':parser.feed(response.text);text='\n'.join(parser.text)
        else:text=response.text
        (ROOT/(sid+'.txt')).write_text(text,encoding='utf-8')
        (ROOT/(sid+'.links.json')).write_text(json.dumps(parser.links,ensure_ascii=False,indent=2),encoding='utf-8')
        item.update(status='downloaded' if len(text)>500 else 'needs_review',raw_file=sid+extension,text_file=sid+'.txt',sha256=hashlib.sha256(raw).hexdigest(),text_chars=len(text))
    except (httpx.HTTPError,OSError) as error:
        item.update(status='failed',error_type=type(error).__name__)
    return item

if __name__=='__main__':
    ROOT.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool:items=list(pool.map(fetch,SOURCES))
    (ROOT/'manifest.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
    for item in items:print(item['id'],item['status'],item.get('text_chars',0),flush=True)
