import sys,json
sys.path.insert(0,'.')
from cl import client
from PIL import Image, ImageDraw
def img(name,color,text):
    im=Image.new('RGB',(640,360),color); ImageDraw.Draw(im).text((20,20),text,fill='white'); im.save(f'media/{name}.png'); return f'media/{name}.png'
c=client()
P=json.load(open('ids.json')) if False else {}
r=c.get('/api/productions'); print(r.text[:300])
prod=r.json()[0] if isinstance(r.json(),list) else r.json()['productions'][0]
pid=prod['id']; proj=prod['source_project_id']; P.update(pid=pid,project=proj)
def node(kind,title,parent=None,**kw):
    r=c.post(f'/api/productions/{pid}/nodes',json={'kind':kind,'title':title,'parent_id':parent,**kw}); print(kind,r.status_code,r.text[:300]); return r.json()
g=node('character','Грэм (тест)',notes='Синтетический таксист, ВАЗ-2106, Минск')
loc=node('location','Аэропорт Минск (тест)',notes='Зал прилёта')
ser=node('series','Серия 1: Трансфер (тест)')
json.dump({**P,'graham':g,'loc':loc,'series':ser},open('ids.json','w'),ensure_ascii=False,indent=1)
