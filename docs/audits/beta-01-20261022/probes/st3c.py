import sys,json
sys.path.insert(0,'.')
from cl import client
c=client(); I=json.load(open('ids.json')); pid=I['pid']; sid=I['series']['id']; g=I['graham']['id']; loc=I['loc']['id']
base=f'/api/productions/{pid}/series/{sid}'
p=c.get(base+'/story-plan').json(); print('plan0',p['revision'],len(p['cards']))
cards=[{'id':f'c{s["number"]}','title':s['title'],'summary':s['summary'],'character_ids':[g],'location_id':loc,'stage':['setup','development','climax','ending'][min(i,3)]} for i,s in enumerate(I['scenes'])]
r=c.put(base+'/story-plan',json={'base_revision':p['revision'],'source':'Producer MOCK','source_kind':'idea','cards':cards}); print('put',r.status_code,r.text[:200])
rev=r.json().get('revision') or c.get(base+'/story-plan').json()['revision']
sb=c.get(base+'/storyboard').json(); print('sb keys',list(sb)[:10]); brev=sb.get('revision') or sb.get('base_revision'); print('board rev',brev, 'scenes',len(sb.get('scenes',[])))
r=c.put(base+'/story-plan',json={'base_revision':0,'cards':cards}); print('stale put',r.status_code,r.text[:120])
r=c.post(base+'/story-plan/preview',json={'plan_revision':rev,'board_revision':brev}); print('preview',r.status_code,r.text[:500])
r=c.post(base+'/story-plan/apply',json={'plan_revision':rev,'board_revision':brev}); print('apply',r.status_code,r.text[:300])
r2=c.post(base+'/story-plan/apply',json={'plan_revision':rev,'board_revision':brev}); print('re-apply stale',r2.status_code,r2.text[:200])
sb2=c.get(base+'/storyboard').json(); print('scenes after',len(sb2.get('scenes',[])),[s.get('title') for s in sb2.get('scenes',[])])
json.dump({**I,'plan_rev':rev},open('ids.json','w'),ensure_ascii=False,indent=1)
