import os,hashlib,json,sqlite3,shutil
src='data'; dst='restore_data'
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
man={}
for r,_,fs in os.walk(src):
    for f in fs:
        if f.startswith('studio.sqlite3'): continue
        p=os.path.join(r,f); man[os.path.relpath(p,src)]=sha(p)
json.dump(man,open('hash_before.json','w',encoding='utf-8'),ensure_ascii=False,indent=0)
print('files hashed',len(man))
assert not os.path.exists(dst)
shutil.copytree(src,dst,ignore=shutil.ignore_patterns('studio.sqlite3*'))
a=sqlite3.connect(src+'/studio.sqlite3'); b=sqlite3.connect(dst+'/studio.sqlite3'); a.backup(b); b.close(); a.close()
print('quick_check',sqlite3.connect(dst+'/studio.sqlite3').execute('PRAGMA quick_check').fetchone())
