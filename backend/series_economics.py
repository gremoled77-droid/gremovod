"""Series totals reuse existing cost/outcome ledgers; estimates remain separate."""
import json
from fastapi import HTTPException
from pydantic import BaseModel,Field


def projects(db,sid):
    return {r['project_id'] for r in db.execute('''SELECT l.project_id FROM production_links l JOIN production_nodes f ON f.id=l.node_id
        JOIN production_nodes s ON s.id=f.parent_id WHERE s.parent_id=? AND s.kind='episode' AND f.kind='frame' ''',(sid,))}


def check_budget(db,project_id,cost):
    parent=db.execute('''SELECT s.parent_id FROM production_links l JOIN production_nodes f ON f.id=l.node_id
        JOIN production_nodes s ON s.id=f.parent_id WHERE l.project_id=? AND f.kind='frame' AND s.kind='episode' ''',(project_id,)).fetchone()
    if not parent:return
    limit=db.execute('SELECT limit_usd FROM production_series_limits WHERE series_id=?',(parent['parent_id'],)).fetchone()
    if not limit or limit['limit_usd'] is None:return
    owned=projects(db,parent['parent_id'])
    reserved=sum(r['estimated_usd'] for r in db.execute('SELECT a.estimated_usd,j.project_id FROM generation_approvals a JOIN jobs j ON j.id=a.job_id') if r['project_id'] in owned)
    from backend import llm_guard
    reserved+=llm_guard.summary(db,owned)['usd']
    if reserved+cost>limit['limit_usd']+1e-9:raise HTTPException(400,'Превышен общий бюджет серии. Измени лимит на доске раскадровки.')


class Limit(BaseModel):
    limit_usd:float|None=Field(default=None,ge=0,le=100000,allow_inf_nan=False)


def register(app,studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS production_series_limits(series_id TEXT PRIMARY KEY,limit_usd REAL)')

    def series(db,pid,sid):
        if not db.execute("SELECT 1 FROM production_nodes WHERE id=? AND production_id=? AND kind='series'",(sid,pid)).fetchone():raise HTTPException(404,'Серия не найдена')

    @app.put('/api/productions/{pid}/series/{sid}/budget')
    def save(pid:str,sid:str,body:Limit):
        with studio.connect() as db:
            series(db,pid,sid)
            db.execute('INSERT INTO production_series_limits(series_id,limit_usd) VALUES(?,?) ON CONFLICT(series_id) DO UPDATE SET limit_usd=excluded.limit_usd',(sid,body.limit_usd))
        return {'saved':True}

    @app.get('/api/productions/{pid}/series/{sid}/economics')
    def report(pid:str,sid:str):
        with studio.connect() as db:
            series(db,pid,sid);owned=projects(db,sid)
            common=db.execute('SELECT source_project_id FROM productions WHERE id=?',(pid,)).fetchone()['source_project_id']
            node_ids={r['id'] for r in db.execute('''SELECT id FROM production_nodes WHERE production_id=? AND
                (id=? OR parent_id=? OR parent_id IN (SELECT id FROM production_nodes WHERE parent_id=?))''',(pid,sid,sid,sid))}
            recipients={r['id']:json.loads(r['request']).get('context',{}).get('entity',{}).get('node_id') for r in db.execute('SELECT id,request FROM native_chat_jobs')}
            limit=db.execute('SELECT limit_usd FROM production_series_limits WHERE series_id=?',(sid,)).fetchone()
            reserved=sum(r['estimated_usd'] for r in db.execute('SELECT a.estimated_usd,j.project_id FROM generation_approvals a JOIN jobs j ON j.id=a.job_id') if r['project_id'] in owned)
            from backend import llm_guard
            llm=llm_guard.summary(db,owned)
        jobs={}
        for project_id in owned|{common}:
            data=studio.report_economics(project_id)
            for job in data['jobs']:
                node=recipients.get(job['id'])
                if (node in node_ids if node else project_id in owned):jobs[job['id']]=job
        items=list(jobs.values())
        unknown=sum(j['actual_usd'] is None and j['provider']!='codex_chat' and j['status']!='cancelled' for j in items)
        finished=[j for j in items if j['kind'] in {'image','video'} and j['status'] not in {'queued','preparing','generating','pending','processing','cancelled','submitting'}]
        used=sum(j['used'] for j in finished)
        return {'series_id':sid,'frame_project_count':len(owned),'actual_usd_known':round(sum(j['actual_usd'] or 0 for j in items),6),
                'estimated_usd':round(sum(j['estimated_usd'] or 0 for j in items),6),'reserved_usd':round(reserved,6),
                'unknown_cost_count':unknown,'costs_complete':unknown==0,'attempts':len(finished),'used_generations':used,
                'success_percent':round(100*used/len(finished),1) if finished else None,
                'chat_api_equivalent_usd':round(sum(j['api_equivalent']['usd'] for j in items if j['api_equivalent']),6),
                'llm':llm,'limit_usd':limit['limit_usd'] if limit else None,'jobs':sorted(items,key=lambda j:j['created_at'],reverse=True)}
