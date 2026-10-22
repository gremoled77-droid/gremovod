import sys,json
sys.path.insert(0,'.')
from cl import client
from PIL import Image, ImageDraw
c=client(); I=json.load(open('ids.json')); pid=I['pid']; sid=I['series']['id']; proj=I['project']
base=f'/api/productions/{pid}/series/{sid}'
sb=c.get(base+'/storyboard').json(); f1=sb['scenes'][0]['frames'][0]['id']; I['f1']=f1
r=c.post('/api/external-jobs',json={'project_id':proj,'request_id':'beta01-ext-job-0001','prompt':'Грэм у ВАЗ-2106 перед зданием аэропорта, кадр 1','node_id':f1,'references':[{'asset_id':I['assets'][0]}]}); print('job',r.status_code,r.text[:300]); job=r.json(); jid=job.get('id') or job['job']['id']
im=Image.new('RGB',(1280,720),'orange'); ImageDraw.Draw(im).text((30,30),'external result',fill='black'); im.save('media/ext.png')
r=c.post(f'/api/external-jobs/{jid}/result',files={'file':('ext.png',open('media/ext.png','rb'),'image/png')},data={'note':'mock'}); print('result',r.status_code,r.text[:300])
e=c.get(f'/api/productions/{pid}/nodes/{f1}/editor').json(); print('files',[(f['kind'],f['asset_id'][:6] if f['asset_id'] else None) for f in e['files']],'jobs',[(j['status'],j['asset_id']) for j in e['jobs']],'data',e['data'],'rev',e['revision'])
I['ext_job']=jid; json.dump(I,open('ids.json','w'),ensure_ascii=False,indent=1)
