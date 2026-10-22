import sys,json
sys.path.insert(0,'.')
from cl import client
c=client(); I=json.load(open('ids.json')); pid=I['pid']; sid=I['series']['id']; g=I['graham']['id']
base=f'/api/productions/{pid}/series/{sid}'
sb=c.get(base+'/storyboard').json(); frames=[f['id'] for f in sb['scenes'][0]['frames']]
for i,f in enumerate(frames,1):
    r=c.post(f'/api/productions/{pid}/nodes/{f}/upload',data={'category':'03_Видео'},files={'file':(f'clip{i}.mp4',open(f'media/clip{i}.mp4','rb'),'video/mp4')}); print('video',i,r.status_code,r.text[:120])
r=c.post(f'/api/productions/{pid}/nodes/{frames[0]}/sound',json={'kind':'voice','text':'Добрый день, куда едем?','hero_node_id':g,'start_s':0.5,'duration_s':2}); print('cue',r.status_code,r.text[:200]); cue=r.json().get('id')
r=c.post(f'/api/productions/{pid}/sound/{cue}/file',files={'file':('voice1.wav',open('media/voice1.wav','rb'),'audio/wav')}); print('cue wav',r.status_code,r.text[:250])
r=c.post(f'/api/productions/{pid}/sound/{cue}/file',files={'file':('x.exe',b'MZ','application/octet-stream')}); print('bad ext',r.status_code)
r=c.get(base+'/sound-list'); print('sound-list',r.status_code,r.text[:300])
r=c.get(base+'/sound'); print('sound',r.status_code,r.text[:400])
el=c.get(base+'/edit-list').json(); print('summary',el['summary']); print('warn',el['warnings']); 
for row in el['rows']: print(row['order'],row['title'],row['video'][-40:],row['duration'])
csv=c.get(base+'/edit-list?format=csv'); print('csv',csv.status_code,len(csv.text)); open('edit-list.csv','w',encoding='utf-8').write(csv.text)
I.update(frames=frames,cue=cue); json.dump(I,open('ids.json','w'),ensure_ascii=False,indent=1)
