import httpx
BASE='http://127.0.0.1:8011'
def client():
    c=httpx.Client(base_url=BASE,timeout=60)
    t=c.get('/api/session').json()['token']; c.headers['x-studio-session']=t
    return c
def svc():
    c=httpx.Client(base_url=BASE,timeout=60); c.headers['authorization']='Bearer '+open('svc_token.txt').read().strip(); return c
