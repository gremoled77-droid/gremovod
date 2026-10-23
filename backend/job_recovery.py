"""Recover a lost submission response using an existing provider task, never a POST generation."""
import json
import re
from fastapi import Header, HTTPException
from pydantic import BaseModel


class Recovery(BaseModel):
    task_id: str
    approved: bool = False


def register(app, studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS job_recoveries(job_id TEXT PRIMARY KEY,task_id TEXT NOT NULL,confirmed_at TEXT NOT NULL)')

    @app.post('/api/jobs/{job_id}/recover')
    async def recover(job_id: str, body: Recovery, x_api_key: str | None = Header(default=None)):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',body.task_id):
            raise HTTPException(400,'Неверный Task ID')
        with studio.connect() as db:
            job=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not job:raise HTTPException(404,'Задание не найдено')
        if job['provider']=='kie':raise HTTPException(409,'Привязка Task ID пока только для PiAPI; задание KIE проверь в кабинете kie.ai')
        if job['task_id']==body.task_id:
            return {'attached':True,'job_id':job_id,'status':job['status'],'upstream':json.loads(job['response'])}
        if job['status'] not in {'submission_unknown','submitting'} or job['task_id']:
            raise HTTPException(409,'Привязка доступна только неопределённой отправке без Task ID')
        result=await studio.request_piapi('GET','/api/v1/task/'+body.task_id,studio.get_key(x_api_key))
        data=result.get('data') or {}
        expected=json.loads(job['request'])['payload']
        actual_input=data.get('input') or {}
        if data.get('task_id')!=body.task_id or any(data.get(k)!=expected.get(k) for k in ('model','task_type')) or actual_input.get('prompt')!=expected['input'].get('prompt'):
            raise HTTPException(409,'Task ID не совпадает с моделью, типом или промптом исходной отправки')
        differences=[k for k,v in expected['input'].items() if actual_input.get(k)!=v]
        if not body.approved:
            return {'attached':False,'task_id':body.task_id,'status':data.get('status'),'provider_input':actual_input,'different_fields':differences,'note':'Сверь референсы и параметры с историей провайдера. Провайдер может заменять URL загруженных изображений. Привязка не запускает генерацию.'}
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            other=db.execute('SELECT id FROM jobs WHERE task_id=? AND id<>?',(body.task_id,job_id)).fetchone()
            if other:raise HTTPException(409,'Этот Task ID уже связан с другим заданием')
            changed=db.execute("UPDATE jobs SET task_id=?,status=?,response=? WHERE id=? AND task_id IS NULL AND status IN ('submission_unknown','submitting')",(body.task_id,data.get('status','pending'),json.dumps(result,ensure_ascii=False),job_id)).rowcount
            if not changed:raise HTTPException(409,'Задание изменилось во время проверки; обнови очередь')
            db.execute('INSERT INTO job_recoveries(job_id,task_id,confirmed_at) VALUES(?,?,?)',(job_id,body.task_id,studio.now()))
        return {'attached':True,'job_id':job_id,'status':data.get('status','pending'),'upstream':result}
