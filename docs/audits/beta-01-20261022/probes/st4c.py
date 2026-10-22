import sys,json
sys.path.insert(0,'.')
from cl import client
from PIL import Image, ImageDraw
c=client(); I=json.load(open('ids.json')); pid=I['pid']; f1=I['f1']
r=c.post(f'/api/productions/{pid}/nodes/{f1}/open-project'); print('open',r.status_code,r.text[:300]); fp=r.json().get('project_id') or r.json().get('id')
r=c.post('/api/external-jobs',json={'project_id':fp,'request_id':'beta01-ext-job-0002','prompt':'Грэм у ВАЗ-2106, кадр 1 v2','node_id':f1}); print('job',r.status_code)
im=Image.new('RGB',(1280,720),'gold'); ImageDraw.Draw(im).text((30,30),'delivered',fill='black'); im.save('media/ext2.png')
r=c.post('/api/external-jobs/beta01-ext-job-0002/result',files={'file':('ext2.png',open('media/ext2.png','rb'),'image/png')}); print('result',r.status_code); new=r.json()['asset']['id']
e=c.get(f'/api/productions/{pid}/nodes/{f1}/editor').json(); print('files',[(f['id'][:6],f['kind'],(f['asset_id'] or '')[:6]) for f in e['files']],'new',new[:6])
fid=[f['id'] for f in e['files'] if f['asset_id']==new]
if fid:
    d=e['data']; r=c.put(f'/api/productions/{pid}/nodes/{f1}/editor',json={'base_revision':e['revision'],'notes':'Главный дубль','character_node_ids':d['character_node_ids'],'location_node_id':d['location_node_id'],'selected_image_file_id':fid[0]}); print('select main',r.status_code,r.text[:200])
    I['main_file']=fid[0]
I.update(frame_project=fp,new_asset=new); json.dump(I,open('ids.json','w'),ensure_ascii=False,indent=1)
