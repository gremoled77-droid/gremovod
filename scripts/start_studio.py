"""Diagnose, reuse running services, start missing services; never install packages."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import build_opener,ProxyHandler
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
OPENER=build_opener(ProxyHandler({}))


def diagnostics():
    problems=[]
    for package in ['fastapi','uvicorn','httpx','pydantic','python-multipart','pillow']:
        try:importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:problems.append('Missing Python dependency: '+package)
    if not shutil.which('node'):problems.append('Node.js not found')
    if not (ROOT/'frontend/node_modules/vite/bin/vite.js').is_file():problems.append('Frontend dependencies missing')
    if not (ROOT/'tools/ffmpeg/bin/ffmpeg.exe').is_file() and not shutil.which('ffmpeg'):problems.append('FFmpeg missing: audio processing unavailable')
    return problems


def occupied(port):
    with socket.socket() as sock:
        sock.settimeout(.3)
        return sock.connect_ex(('127.0.0.1',port))==0


def probe(port):
    path='/api/health' if port==8000 else '/'
    try:
        with OPENER.open(f'http://127.0.0.1:{port}{path}',timeout=2) as response:
            data=response.read(16384)
            if port==8000:return bool(json.loads(data).get('ok'))
            return b'AI Workflow Studio' in data and (b'/@vite/client' in data or b'/src/' in data)
    except Exception:return False


def start(dev=False):
    issues=diagnostics()
    if issues:raise RuntimeError('\n'.join(issues)+'\nRun INSTALL_WINDOWS.bat to install dependencies. No installation was started.')
    for port in [8000,5173]:
        if occupied(port) and not probe(port):raise RuntimeError(f'Port {port} is used by another service. Close that service or change the studio port configuration.')
    runtime=ROOT/'runtime/startup';runtime.mkdir(parents=True,exist_ok=True)
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    launched=[]
    launch_env=os.environ.copy();launch_env['PATH']=str(ROOT/'tools/ffmpeg/bin')+os.pathsep+launch_env.get('PATH','')
    for port in [8000,5173]:
        if probe(port):print(f'Service {port}: already running');continue
        command=[sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000','--no-access-log']+(['--reload','--reload-dir',str(ROOT/'backend')] if dev else []) if port==8000 else [shutil.which('node') or 'node',str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'--host','0.0.0.0' if os.environ.get('STUDIO_REMOTE_HOSTS') else '127.0.0.1','--port','5173','--strictPort']
        cwd=ROOT if port==8000 else ROOT/'frontend'
        with (runtime/f'{port}.log').open('a',encoding='utf-8') as log:
            process=subprocess.Popen(command,cwd=cwd,env=launch_env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)
        launched.append({'port':port,'pid':process.pid})
        for _ in range(60):
            if probe(port):break
            if process.poll() is not None:raise RuntimeError(f'Service {port} stopped. See runtime/startup/{port}.log')
            time.sleep(.25)
        else:raise RuntimeError(f'Service {port} did not become ready. See runtime/startup/{port}.log')
        print(f'Service {port}: ready')
    (runtime/'last-launch.json').write_text(json.dumps(launched),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--no-browser',action='store_true');parser.add_argument('--dev',action='store_true',help='backend restarts itself after code changes');args=parser.parse_args()
    try:
        if args.check:
            issues=diagnostics()
            print('\n'.join(issues) if issues else 'Dependencies OK; no installation or service launch performed.')
            sys.exit(bool(issues))
        start(args.dev)
        if not args.no_browser:webbrowser.open('http://127.0.0.1:5173/')
    except Exception as exc:
        print(str(exc));sys.exit(1)
