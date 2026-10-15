"""Read-only task monitoring and durable, bounded retries for output downloads."""
import asyncio
import json
import time
from fastapi import HTTPException

ENABLED = True


async def deliver(studio, job_id):
    with studio.connect() as db:
        job=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        previous=db.execute('SELECT * FROM job_delivery WHERE job_id=?',(job_id,)).fetchone()
    if not job or job['status']!='completed':return
    urls=studio.output_urls(json.loads(job['response']),job['kind'])
    attempts=(previous['attempts'] if previous else 0)+1
    error='';saved=0
    try:
        if not urls:raise HTTPException(502,'Провайдер сообщил completed без ссылок на результаты')
        for index in range(len(urls)):
            await studio.save_job_image(job_id,index)
            saved+=1
    except (HTTPException,OSError,ValueError) as exc:
        error=str(exc.detail) if isinstance(exc,HTTPException) else 'Ошибка локального сохранения: '+type(exc).__name__
    state='saved' if not error else ('retry' if attempts<5 else 'attention')
    with studio.connect() as db:
        db.execute('''INSERT INTO job_delivery(job_id,state,attempts,saved,total,error,next_retry) VALUES(?,?,?,?,?,?,?)
                      ON CONFLICT(job_id) DO UPDATE SET state=excluded.state,attempts=excluded.attempts,saved=excluded.saved,total=excluded.total,error=excluded.error,next_retry=excluded.next_retry''',
                   (job_id,state,attempts,saved,len(urls),error,time.time()+min(1800,30*2**(attempts-1))))


async def cycle(studio):
    with studio.connect() as db:
        jobs=db.execute("SELECT j.id,j.status FROM jobs j LEFT JOIN job_delivery d ON d.job_id=j.id WHERE j.task_id IS NOT NULL AND j.status NOT IN ('failed','submission_unknown') AND (d.state IS NULL OR (d.state='retry' AND d.next_retry<=?)) ORDER BY j.created_at LIMIT 20",(time.time(),)).fetchall()
    for job in jobs:
        try:
            if job['status']!='completed':await studio.job_status(job['id'],None)
            await deliver(studio,job['id'])
        except HTTPException:
            # Provider GET failed; it is safe to check again, never submit a new job.
            continue


def register(app,studio):
    @app.on_event('startup')
    async def start():
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS job_delivery(job_id TEXT PRIMARY KEY,state TEXT NOT NULL,attempts INTEGER NOT NULL,saved INTEGER NOT NULL,total INTEGER NOT NULL,error TEXT NOT NULL,next_retry REAL NOT NULL)''')
        async def monitor():
            while True:
                await asyncio.sleep(30)
                try:await cycle(studio)
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception('Task monitor failed; no generation was submitted')
        if ENABLED:app.state.delivery_monitor=asyncio.create_task(monitor())

    @app.on_event('shutdown')
    async def stop():
        task=getattr(app.state,'delivery_monitor',None)
        if task:
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
            app.state.delivery_monitor=None

    @app.post('/api/jobs/{job_id}/retry-download')
    async def retry(job_id:str):
        with studio.connect() as db:
            row=db.execute('SELECT status FROM jobs WHERE id=?',(job_id,)).fetchone()
            if not row:raise HTTPException(404,'Задание не найдено')
            if row['status']!='completed':raise HTTPException(409,'Результат ещё не готов')
            db.execute('DELETE FROM job_delivery WHERE job_id=?',(job_id,))
        await deliver(studio,job_id)
        return {'generation_submitted':False}
