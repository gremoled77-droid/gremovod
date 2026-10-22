import sys,json
sys.path.insert(0,'.')
from cl import client
from PIL import Image, ImageDraw
def img(name,color,text):
    im=Image.new('RGB',(640,360),color); ImageDraw.Draw(im).text((20,20),text,fill='white'); im.save(f'media/{name}.png'); return f'media/{name}.png'
c=client(); I=json.load(open('ids.json')); proj=I['project']; cid=I['graham']['character_id']
# state with characters
st=c.get(f'/api/projects/{proj}').json(); print('keys',list(st)[:8],'rev',st.get('revision'))
state=st['state']; state['characters']=[{'id':cid,'name':'Грэм','identity':{'role':'таксист','car':'ВАЗ-2106','city':'Минск'}}]
r=c.post('/api/projects',json={'id':proj,'title':st.get('title','BETA01'),'state':state,'base_revision':st['revision']}); print('save',r.status_code,r.text)
def asset(name,color,cat):
    p=img(name,color,name)
    r=c.post(f'/api/characters/{proj}/{cid}/assets',files={'file':(name+'.png',open(p,'rb'),'image/png')},data={'category':cat,'note':name}); print(name,cat,r.status_code,r.text[:200]); return r.json()
a=asset('ref_ok','navy','approved_generations'); b=asset('ref_cand','darkred','candidate_generations'); real=asset('ref_real','darkgreen','real_references')
I.update(ref_ok=a['id'],ref_cand=b['id'],ref_real=real['id']); json.dump(I,open('ids.json','w'),ensure_ascii=False,indent=1)
