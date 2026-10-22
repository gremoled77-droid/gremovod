import sys,json
sys.path.insert(0,'.')
from cl import client
from PIL import Image, ImageDraw
def img(name,color):
    im=Image.new('RGB',(1280,720),color); ImageDraw.Draw(im).text((30,30),name,fill='white'); im.save(f'media/{name}.png'); return f'media/{name}.png'
c=client(); I=json.load(open('ids.json')); pid=I['pid']; sid=I['series']['id']; proj=I['project']; g=I['graham']['id']; loc=I['loc']['id']
base=f'/api/productions/{pid}/series/{sid}'
sb=c.get(base+'/storyboard').json(); scene1=sb['scenes'][0]; print('scene keys',list(scene1)[:12])
sid1=scene1.get('id') or scene1['node']['id']
assets=[]
for n,col in [('shot1','teal'),('shot2','purple'),('shot3','brown')]:
    r=c.post('/api/library/import-image',data={'project_id':proj},files={'file':(n+'.png',open(img(n,col),'rb'),'image/png')}); print(n,r.status_code,r.text[:160]); assets.append(r.json().get('id') or r.json().get('asset',{}).get('id'))
r=c.post(base+'/storyboard/frames',json={'base_revision':sb['revision'],'request_id':'beta01-frames-0001','scene_id':sid1,'frames':[{'asset_id':a,'title':f'Кадр {i+1}'} for i,a in enumerate(assets)],'character_node_ids':[g],'location_node_id':loc}); print('frames',r.status_code,r.text[:400])
r2=c.post(base+'/storyboard/frames',json={'base_revision':sb['revision'],'request_id':'beta01-frames-0001','scene_id':sid1,'frames':[{'asset_id':a,'title':f'Кадр {i+1}'} for i,a in enumerate(assets)],'character_node_ids':[g],'location_node_id':loc}); print('replay',r2.status_code,r2.json().get('replayed'))
I.update(assets=assets,scene1=sid1); json.dump(I,open('ids.json','w'),ensure_ascii=False,indent=1)
sb=c.get(base+'/storyboard').json(); print(json.dumps(sb['scenes'][0],ensure_ascii=False)[:900])
