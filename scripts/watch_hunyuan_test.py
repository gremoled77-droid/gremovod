"""Monitor the ONE approved live test; never submits or retries generation."""
import json
import time
from datetime import datetime,timezone
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
MARKER=ROOT/'runtime/hunyuan-test-2026-10-15.json'
JOB='hunyuan-minsk-live-20261015-01'

def main():
    record=json.loads(MARKER.read_text(encoding='utf-8'))
    if record['body']['request_id']!=JOB:raise RuntimeError('Unexpected test ID')
    end=time.monotonic()+900
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=180) as client:
        while time.monotonic()<end:
            r=client.get('/api/jobs/'+JOB);r.raise_for_status()
            result=r.json();data=result.get('upstream',{}).get('data') or {}
            state=data.get('status',record.get('result',{}).get('status','unknown'))
            record.update(last_checked_at=datetime.now(timezone.utc).isoformat(),last_status=state,last_result=result)
            MARKER.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'status':state,'checked_at':record['last_checked_at']},ensure_ascii=False),flush=True)
            if state=='completed':
                response=client.post(f'/api/jobs/{JOB}/outputs/0/save');response.raise_for_status()
                asset=response.json();record.update(phase='completed_and_saved',asset=asset)
                MARKER.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
                meta=asset['metadata'];path=(ROOT/'backend/library'/asset['filename']).resolve()
                report=f'''# Hunyuan — реальный тест 15.10.2026

Одна попытка, подтверждённый пользователем бюджет: $0.09.
Проект: {record['body']['project_id']}
Job ID: {JOB}
PiAPI task ID: {data.get('task_id')}
Модель: Qubico/hunyuan, img2video-replace.
Статус: completed; оригинал сохранён и проверен FFprobe.
Файл: {path}
Размер: {meta['width']}×{meta['height']}; длительность: {meta['duration']} сек.
Цена по документации: $0.09 за генерацию. Резерв и фактический consume
в единицах провайдера сохранены в runtime/hunyuan-test-2026-10-15.json.
Проверка отдельного долларового списания по балансу не выполнялась.
Оригинал исходного кадра сохранён; итог не помечен как использованный в ролике.
Повторная генерация не выполнялась.

Источник схемы и цены: https://piapi.ai/docs/hunyuan-video/txt2video-api
'''
                (ROOT/'docs/HUNYUAN_LIVE_TEST_2026-10-15.md').write_text(report,encoding='utf-8')
                print(json.dumps({'saved':str(path),'width':meta['width'],'height':meta['height'],'duration':meta['duration'],'asset_id':asset['id'],'usage':(data.get('meta') or {}).get('usage')},ensure_ascii=False),flush=True)
                return
            if state in {'failed','cancelled','submission_unknown'}:
                print(json.dumps({'error':data.get('error'),'generation_retried':False},ensure_ascii=False),flush=True)
                return
            time.sleep(30)
    print('Monitoring window ended; the task was not resubmitted.',flush=True)

if __name__=='__main__':main()
