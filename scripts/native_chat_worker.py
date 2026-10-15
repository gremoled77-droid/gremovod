"""Local transport for the dedicated Codex chat, not an LLM or image generator.

For operation=prompt the chat calls wait, prepares a prompt, calls prompt-ready,
then STOPS. Only operation=generate/edit may proceed to built-in imagegen and
upload the original with image. No paid API fallback.
"""
import argparse
import json
import time
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8000/api/chatgpt/worker'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['wait','prompt-ready','identity-ready','image','failed'])
    parser.add_argument('--seconds',type=int,default=50)
    parser.add_argument('--job')
    parser.add_argument('--file',type=Path)
    parser.add_argument('--message',default='')
    args=parser.parse_args()
    token=(ROOT/'runtime/prompt-chat/worker-token.txt').read_text(encoding='utf-8').strip()
    with httpx.Client(headers={'X-Studio-Worker':token},timeout=60) as client:
        if args.action=='wait':
            end=time.monotonic()+max(0,min(args.seconds,55))
            while True:
                r=client.post(BASE+'/claim');r.raise_for_status();data=r.json()
                if data.get('job') or time.monotonic()>=end:break
                time.sleep(2)
        else:
            if not args.job:parser.error('--job is required')
            if args.action=='image':
                if not args.file:parser.error('--file is required')
                with args.file.open('rb') as file:
                    r=client.post(BASE+'/jobs/'+args.job+'/image',files={'file':(args.file.name,file)},data={'actual_model':'not_exposed'})
            elif args.action=='identity-ready':
                if not args.file:parser.error('--file is required')
                identity=json.loads(args.file.read_text(encoding='utf-8-sig'))
                r=client.post(BASE+'/jobs/'+args.job+'/progress',json={'status':'identity_ready','identity':identity,'message':args.message or 'Описание распознано по референсам'})
            else:
                if args.action=='prompt-ready' and not args.file:parser.error('--file is required')
                prompt=args.file.read_text(encoding='utf-8-sig') if args.action=='prompt-ready' else ''
                r=client.post(BASE+'/jobs/'+args.job+'/progress',json={'status':'prompt_ready' if args.action=='prompt-ready' else 'failed','prompt':prompt,'message':args.message})
            r.raise_for_status();data=r.json()
        print(json.dumps(data,ensure_ascii=False))

if __name__=='__main__':main()
