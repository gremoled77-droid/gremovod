"""Per-clip costs and final-use outcomes. Estimates never become actual charges."""
import json
from fastapi import HTTPException
from pydantic import BaseModel, Field
from backend.image_pricing import api_equivalent

class Cost(BaseModel):
    actual_usd: float | None = Field(default=None,ge=0,le=100000,allow_inf_nan=False)
    note: str = Field(default='',max_length=1000)

class Decision(BaseModel):
    decision: str

def free_provider(provider):
    """Попытки без оплаты по API: чат Codex и ручная внешняя генерация."""
    return provider=='codex_chat' or provider.startswith('external:')

def register(app,studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS clip_costs(job_id TEXT PRIMARY KEY,actual_usd REAL,note TEXT NOT NULL,updated_at TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS asset_outcomes(asset_id TEXT PRIMARY KEY,decision TEXT NOT NULL,updated_at TEXT NOT NULL)')

    @app.put('/api/economics/jobs/{job_id}')
    def cost(job_id:str,body:Cost):
        with studio.connect() as db:
            exists=db.execute('SELECT 1 FROM jobs WHERE id=?',(job_id,)).fetchone() or db.execute('SELECT 1 FROM native_chat_jobs WHERE id=?',(job_id,)).fetchone() or db.execute('SELECT 1 FROM prompt_versions WHERE id=?',(job_id,)).fetchone()
            if not exists:raise HTTPException(404,'Задание не найдено')
            db.execute('INSERT INTO clip_costs VALUES(?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET actual_usd=excluded.actual_usd,note=excluded.note,updated_at=excluded.updated_at',(job_id,body.actual_usd,body.note,studio.now()))
        return {'saved':True}

    @app.put('/api/economics/assets/{asset_id}')
    def outcome(asset_id:str,body:Decision):
        if body.decision not in {'used','rejected','undecided'}:raise HTTPException(400,'Неизвестная оценка')
        with studio.connect() as db:
            if not db.execute('SELECT 1 FROM library_assets WHERE id=?',(asset_id,)).fetchone():raise HTTPException(404,'Ассет не найден')
            db.execute('INSERT INTO asset_outcomes VALUES(?,?,?) ON CONFLICT(asset_id) DO UPDATE SET decision=excluded.decision,updated_at=excluded.updated_at',(asset_id,body.decision,studio.now()))
        return {'saved':True,'decision':body.decision}

    @app.get('/api/economics')
    def report(project_id:str):
        studio.project(project_id)
        with studio.connect() as db:
            rows=db.execute('SELECT j.id,j.status,j.kind,j.provider,j.request,j.created_at,a.estimated_usd FROM jobs j LEFT JOIN generation_approvals a ON a.job_id=j.id WHERE j.project_id=?',(project_id,)).fetchall()
            native=db.execute("SELECT id,status,operation,target,created_at FROM native_chat_jobs WHERE project_id=? AND operation!='describe_character'",(project_id,)).fetchall()
            prompts=db.execute("SELECT id,target,provider,created_at FROM prompt_versions WHERE project_id=? AND provider!='codex_chat'",(project_id,)).fetchall()
            external=db.execute('SELECT id,status,target,service,created_at FROM external_jobs WHERE project_id=?',(project_id,)).fetchall()
            costs={x['job_id']:dict(x) for x in db.execute('SELECT * FROM clip_costs')}
            assets=[dict(x) for x in db.execute("SELECT a.id,a.job_id,a.metadata,COALESCE(o.decision,'undecided') AS decision FROM library_assets a LEFT JOIN asset_outcomes o ON o.asset_id=a.id WHERE a.project_id=?",(project_id,))]
        attempts=[]
        for row in rows:
            data=json.loads(row['request'])
            target=data.get('payload',{}).get('task_type') or data.get('model_id') or data.get('voice',{}).get('model') or row['kind']
            attempts.append({'id':row['id'],'status':row['status'],'provider':row['provider'],'target':target,'kind':row['kind'],'created_at':row['created_at'],'estimated_usd':row['estimated_usd']})
        for row in native:
            attempts.append({'id':row['id'],'status':row['status'],'provider':'codex_chat','target':row['target'],'kind':'image' if row['operation'] in {'generate','edit'} else 'prompt','created_at':row['created_at'],'estimated_usd':None})
        for row in external:
            status={'received':'completed','waiting_external':'queued'}.get(row['status'],row['status'])
            attempts.append({'id':row['id'],'status':status,'provider':'external:'+row['service'],'target':row['target'],'kind':'image','created_at':row['created_at'],'estimated_usd':None})
        for row in prompts:
            attempts.append({'id':row['id'],'status':'completed','provider':row['provider'],'target':row['target']+' · prompt','kind':'prompt','created_at':row['created_at'],'estimated_usd':None})
        for attempt in attempts:
            cost=costs.get(attempt['id'],{})
            attempt.update(actual_usd=cost.get('actual_usd'),cost_note=cost.get('note',''))
            outputs=[x for x in assets if x['job_id']==attempt['id']]
            attempt['used']=any(x['decision']=='used' for x in outputs)
            attempt['rejected']=bool(outputs) and all(x['decision']=='rejected' for x in outputs)
            attempt['api_equivalent']=None
            if free_provider(attempt['provider']) and attempt['kind']=='image' and attempt['status']=='completed':
                meta=json.loads(outputs[0]['metadata']) if outputs else {}
                attempt['api_equivalent']=api_equivalent(meta.get('width'),meta.get('height'),attempt['target'])
        media=[x for x in attempts if x['kind'] in {'image','video'} and x['status'] not in {'queued','preparing','generating','pending','processing','cancelled','submitting'}]
        used=sum(x['used'] for x in media)
        known=[x for x in attempts if x['actual_usd'] is not None]
        actual=sum(x['actual_usd'] for x in known)
        # Chat use is counted, but does not require a per-image charge or subscription allocation.
        unknown=sum(x['actual_usd'] is None for x in attempts if x['status']!='cancelled' and not free_provider(x['provider']))
        llm_unpriced=sum(x['actual_usd'] is None for x in attempts if x['kind']=='prompt' and x['status']!='cancelled' and not free_provider(x['provider']))
        media_unknown=sum(x['actual_usd'] is None for x in attempts if x['kind'] in {'image','video','audio'} and x['status']!='cancelled' and not free_provider(x['provider']))
        periods={}
        for x in media:
            key=(x['created_at'][:7],x['target'])
            bucket=periods.setdefault(key,{'month':key[0],'model':key[1],'attempts':0,'used':0,'actual_usd':0,'unknown_costs':0})
            bucket['attempts']+=1;bucket['used']+=int(x['used']);bucket['actual_usd']+=x['actual_usd'] or 0;bucket['unknown_costs']+=int(x['actual_usd'] is None and not free_provider(x['provider']))
        chat_images=[x for x in attempts if x['api_equivalent']]
        from backend import llm_gateway, llm_guard
        with studio.connect() as db:
            # четыре раздельных итога: факт, резерв, неизвестные списания и неденежный ориентир
            llm={**llm_guard.summary(db,{project_id}),**llm_gateway.summarize_spend(db,[project_id])}
        return {'llm':llm,'project_id':project_id,'actual_usd_known':round(actual,6),'costs_complete':unknown==0,
                'chat_image_count':len(chat_images),'chat_api_equivalent_usd':round(sum(x['api_equivalent']['usd'] for x in chat_images),6),
                'unknown_cost_count':unknown,'llm_calls_unpriced':llm_unpriced,'media_costs_complete':media_unknown==0,'unknown_generation_cost_count':media_unknown,'estimated_usd':round(sum(x['estimated_usd'] or 0 for x in attempts),6),
                'attempts':len(media),'used_generations':used,'success_percent':round(100*used/len(media),1) if media else None,
                'cost_per_used_result_known':round(actual/used,6) if used else None,
                'assets':assets,'jobs':sorted(attempts,key=lambda x:x['created_at'],reverse=True),'progress':sorted(periods.values(),key=lambda x:(x['month'],x['model']))}

    studio.report_economics=report
