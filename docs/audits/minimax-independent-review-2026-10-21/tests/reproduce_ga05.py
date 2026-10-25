import asyncio
import ipaddress
import json
import os
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from backend import main, remote_access, test_smoke

test = test_smoke.StudioSmokeTests()
test.setUp()
try:
    env = {'STUDIO_REMOTE_HOSTS': 'studio.example.com', 'STUDIO_ACCESS_PASSWORD': 'correct-horse-battery'}
    for wrapped in (False, True):
        remote_access._fails.clear()
        app = ProxyHeadersMiddleware(main.app, trusted_hosts='*') if wrapped else main.app
        client = TestClient(app, base_url='https://studio.example.com', client=('198.51.100.20', 12345))
        with patch.dict(os.environ, env):
            statuses = [client.post('/api/login', json={'password':'wrong'}, headers={'X-Forwarded-For': f'203.0.113.{i}'}).status_code for i in range(1,8)]
        print(json.dumps({'case':'uvicorn_wildcard' if wrapped else 'bare_asgi', 'statuses':statuses}))
        assert statuses == ([401]*7 if wrapped else [401]*5+[429]*2)
        client.close()
        client = TestClient(app, base_url='http://127.0.0.1', client=('198.51.100.20', 12345))
        with patch.dict(os.environ, env):
            session = client.get('/api/session', headers={'X-Forwarded-For':'127.0.0.1'})
            headers = {'X-Forwarded-For':'127.0.0.1'}
            if session.status_code == 200:
                headers['X-Studio-Session'] = session.json()['token']
            projects = client.get('/api/projects', headers=headers)
        print(json.dumps({'case':'uvicorn_loopback_spoof' if wrapped else 'bare_loopback_spoof', 'session_status':session.status_code, 'projects_status':projects.status_code}))
        assert projects.status_code == (200 if wrapped else 401)
        client.close()
    networks = [ipaddress.ip_network('10.0.0.2')]
    for value in ('203.0.113.7, invalid, 198.51.100.20', '203.0.113.7, 198.51.100.20'):
        request = SimpleNamespace(client=SimpleNamespace(host='10.0.0.2'), headers={'x-forwarded-for': value})
        identity = remote_access.client_ip(request, networks, 2)
        print(json.dumps({'case':'proxy_chain_hops2', 'header':value, 'identity':identity}))
        assert identity == '203.0.113.7'
    for value in ('[2001:db8::7]:bad', '[2001:db8::7]:999999', '[2001:db8::7]trailing'):
        parsed = remote_access._parse_ip(value)
        print(json.dumps({'case':'invalid_bracket_port', 'input':value, 'parsed':str(parsed)}))
        assert parsed is not None
finally:
    test.tearDown()
