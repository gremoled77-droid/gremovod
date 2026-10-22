import sys,json,hashlib,os
sys.path.insert(0,'.')
exec(open('st6.py',encoding='utf-8').read().split("A=[a for a")[0])   # helpers only
def freeze(a,rid,rights=True):
    r=svc().post('/api/qa/reviews',json={'project_id':proj,'task_id':'beta01-task','artifact_id':a['id'],'artifact_revision':'r1','review_phase':'FINAL_MEDIA','requested_scopes':['VIDEO','AUDIO'],'request_id':rid,'media_asset_id':a['id'],'required_modalities':['VIDEO','AUDIO'],'processing_rights_confirmed':rights}); j=r.json()
    rv=j.get('review',{}); print(' freeze',r.status_code,j.get('media_status'),'|',j.get('media_reason'),'| master',str(rv.get('master_sha256'))[:12],'qc',rv.get('qc_verdict'),'snap',(j.get('snapshot_hash') or '')[:10]); return j
arts={a['title']:a for a in c.get(f'/api/projects/{proj}/release-artifacts').json()}
A,N=arts['Master A'],arts['NoAudio']
print('A file sha',sha('media/master.mp4')[:12]); qc(A); fa=freeze(A,'beta01-fz-A-0001')
print('--- no audio'); n=qc(N); print('  reason:',n.get('reason')); freeze(N,'beta01-fz-N-0001')
print('--- no processing rights'); qc(A); freeze(A,'beta01-fz-A-0002',rights=False)
print('--- QC FAIL'); qc(A,{**MAN,'width':1920,'height':1080}); freeze(A,'beta01-fz-A-0003'); qc(A)
print('--- tamper after QC+freeze'); C=imp('media/master_c.mp4','Master C'); qc(C); fc=freeze(C,'beta01-fz-C-0001')
p=f"data/library/{C['library_asset_id']}.mp4"; open(p,'ab').write(b'\0'); print(' tampered sha',sha(p)[:12]); freeze(C,'beta01-fz-C-0002')
g=c.get(f'/api/projects/{proj}/release-artifacts/{C["id"]}/qc').json(); print(' stored QC verdict',g['verdict'],g['reason'],'sha',g['master_sha256'][:12])
print('--- old review for C still says master',str(fc['review'].get('master_sha256'))[:12])
I=json.load(open('ids.json',encoding='utf-8')); I.update(artA=A,artN=N,artC=C); json.dump(I,open('ids.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
