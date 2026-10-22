import sys,json,os,hashlib
sys.path.insert(0,'.')
import cl; cl.BASE='http://127.0.0.1:8012'
from cl import client,svc
c=client(); I=json.load(open('ids.json',encoding='utf-8')); pid=I['pid']; sid=I['series']['id']; proj=I['project']
print('health',c.get('/api/health').json())
p=c.get(f'/api/projects/{proj}').json(); print('project rev',p['revision'],'scenario:',bool(p['state'].get('scenario')),'logline ok',bool(p['state']['scenario']['logline']))
sb=c.get(f'/api/productions/{pid}/series/{sid}/storyboard').json(); print('scenes',[s['title'] for s in sb['scenes']],'frames s1',len(sb['scenes'][0]['frames']))
sp=c.get(f'/api/productions/{pid}/series/{sid}/story-plan').json(); print('plan rev',sp['revision'],'cards',len(sp['cards']),'scene_ids set',all(x['scene_id'] for x in sp['cards']))
el=c.get(f'/api/productions/{pid}/series/{sid}/edit-list').json(); print('edit-list',el['summary'],el['warnings'])
f1=sb['scenes'][0]['frames'][0]['id']; e=c.get(f'/api/productions/{pid}/nodes/{f1}/editor').json(); print('frame1 main take',e['data']['selected_image_file_id']==I.get('main_file'),'files',len(e['files']))
snd=c.get(f'/api/productions/{pid}/series/{sid}/sound-list').text.splitlines(); print('sound-list',snd[1])
arts={a['title']:a for a in c.get(f'/api/projects/{proj}/release-artifacts').json()}; print('artifacts',list(arts))
q=c.get(f'/api/projects/{proj}/release-artifacts/{arts["Master A"]["id"]}/qc').json(); print('QC A',q['verdict'],q['master_sha256'][:12])
before=json.load(open('hash_before.json',encoding='utf-8')); bad=[]
for rel,h in before.items():
    pth=os.path.join('restore_data',rel); 
    if not os.path.isfile(pth): bad.append(('missing',rel)); continue
    if hashlib.sha256(open(pth,'rb').read()).hexdigest()!=h: bad.append(('diff',rel))
print('hash compare: files',len(before),'mismatch',bad)
# post-restore: tamper scenario with FIXED code
C=arts['Master C']; r=svc().post('/api/qa/reviews',json={'project_id':proj,'task_id':'beta01-task','artifact_id':C['id'],'artifact_revision':'r1','review_phase':'FINAL_MEDIA','requested_scopes':['VIDEO','AUDIO'],'request_id':'beta01-fz-C-0003','media_asset_id':C['id'],'required_modalities':['VIDEO','AUDIO'],'processing_rights_confirmed':True}); j=r.json(); print('freeze tampered C (fixed code):',j.get('media_status'),'|',j.get('media_reason'))
A=arts['Master A']; r=svc().post('/api/qa/reviews',json={'project_id':proj,'task_id':'beta01-task','artifact_id':A['id'],'artifact_revision':'r1','review_phase':'FINAL_MEDIA','requested_scopes':['VIDEO','AUDIO'],'request_id':'beta01-fz-A-0009','media_asset_id':A['id'],'required_modalities':['VIDEO','AUDIO'],'processing_rights_confirmed':True}); j=r.json(); print('freeze untouched A:',j.get('media_status'),(j.get('snapshot_hash') or '')[:10])
