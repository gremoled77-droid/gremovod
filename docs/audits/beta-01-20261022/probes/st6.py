import sys,json,hashlib,os
sys.path.insert(0,'.')
from cl import client,svc
c=client(); I=json.load(open('ids.json')); proj=I['project']
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
def rev(): return c.get(f'/api/projects/{proj}').json()['revision']
def imp(path,title):
    r=c.post(f'/api/projects/{proj}/release-artifacts',data={'project_revision':rev(),'title':title},files={'file':(os.path.basename(path),open(path,'rb'),'video/mp4')}); print('import',title,r.status_code,r.text[:260] if r.status_code!=200 else {k:r.json()[k] for k in ('id','status','width','height','duration','library_asset_id')}); return r.json()
MAN={'width':1280,'height':720,'fps':25,'duration_ms':9000,'container':'mp4','video_codec':'h264','audio_codec':'aac','require_audio':True}
def qc(a,man=MAN):
    r=c.post(f'/api/projects/{proj}/release-artifacts/{a["id"]}/qc/measure',json={'manifest':man}); j=r.json(); print(' qc',r.status_code,j.get('verdict'),json.dumps(j.get('checks'),ensure_ascii=False)[:260] if r.status_code==200 else r.text[:200]); return j
def freeze(a,rid):
    r=svc().post('/api/qa/reviews',json={'project_id':proj,'task_id':'beta01-task','artifact_id':a['id'],'artifact_revision':'r1','review_phase':'FINAL_MEDIA','requested_scopes':['VIDEO','AUDIO'],'request_id':rid,'media_asset_id':a['library_asset_id'],'required_modalities':['VIDEO','AUDIO'],'processing_rights_confirmed':True}); j=r.json(); print(' freeze',r.status_code,j.get('media_status'),j.get('media_reason'),(j.get('snapshot_hash') or '')[:10]); return j
A=[a for a in c.get(f'/api/projects/{proj}/release-artifacts').json() if a['title']=='Master A'][0]; print('A sha',sha('media/master.mp4')[:12]); qa=qc(A); print(' sha in qc:',json.dumps(qa)[:0]); 
g=c.get(f'/api/projects/{proj}/release-artifacts/{A["id"]}/qc').json(); print(' GET qc keys',list(g)); print(' qc sha',str(g.get('master_sha256') or g.get('sha256') or g.get('measurements',{}).get('sha256'))[:12])
fa=freeze(A,'beta01-freeze-A-0001'); print(' review master sha',str(fa['review'].get('master_sha256'))[:12],'qc',fa['review'].get('qc_verdict'))
print('--- neg: no audio'); N=imp('media/master_noaudio.mp4','NoAudio'); qc(N); freeze(N,'beta01-freeze-N-0001')
print('--- neg: FAIL manifest'); F=qc(A,{**MAN,'width':1920,'height':1080}); freeze(A,'beta01-freeze-A-0002')
print('--- neg: tamper after QC'); B=imp('media/master_b.mp4','Master B'); qc(B)
import glob
lib=os.path.join('data','media','library')
cands=[p for p in glob.glob('data/**/'+B['library_asset_id']+'*',recursive=True)]; print(' file',cands)
open(cands[0],'ab').write(b'\0'); print(' tampered; remeasure:'); tb=qc(B); freeze(B,'beta01-freeze-B-0001')
I.update(artA=A,artN=N,artB=B); json.dump(I,open('ids.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
