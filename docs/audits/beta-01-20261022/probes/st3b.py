import sys,json,datetime
sys.path.insert(0,'.')
from cl import client
c=client(); I=json.load(open('ids.json')); proj=I['project']; cid=I['graham']['character_id']
base=dict(project_id=proj,idea='Грэм встречает пассажира в аэропорту Минск и везёт его в центр на ВАЗ-2106',character_ids=[cid],provider='mock',model='mock-producer',duration_seconds=60,language='ru')
def run(**kw):
    r=c.post('/api/producer/run',json={**base,**kw}); return r
r=run(reference_ids=[I['ref_ok']]); print('approved ref',r.status_code,r.text[:150]); res=r.json()
print('cost',res['cost_usd'],'ext',res['external_calls'],'scenes',len(res['scenes']),'beats',len(res['beats']))
for name,ids in [('candidate',[I['ref_cand']]),('unknown',['deadbeef']),('real',[I['ref_real']])]:
    r=run(reference_ids=ids); print(name,r.status_code,r.text[:110])
# other-character / foreign project ref: no second character -> skip
r=c.post('/api/producer/run',json={**base,'reference_ids':[I['ref_ok']],'character_ids':[]}); print('ref w/o selected char',r.status_code,r.text[:110])
# paid path without approval must be refused
r=c.post('/api/producer/run',json={**base,'provider':'','model':'gpt-5.6-luna'}); print('paid unapproved',r.status_code,r.text[:140])
# save scenario into state
st=c.get(f'/api/projects/{proj}').json(); state=st['state']; state['scenario']={**res,'saved_at':datetime.datetime.utcnow().isoformat()}
r=c.post('/api/projects',json={'id':proj,'title':st['title'],'state':state,'base_revision':st['revision']}); print('save scenario',r.status_code,r.text)
r=c.post('/api/projects',json={'id':proj,'title':st['title'],'state':state,'base_revision':st['revision']}); print('stale save',r.status_code,r.text[:150])
I['scenes']=[(s) for s in res['scenes']]; json.dump(I,open('ids.json','w'),ensure_ascii=False,indent=1)
print(json.dumps(res['scenes'][0],ensure_ascii=False)[:400])
