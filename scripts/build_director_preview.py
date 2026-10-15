"""Refresh the isolated Vite review page from the real backend catalogues.

Run from the workspace root: .venv/Scripts/python.exe scripts/build_director_preview.py
This script never opens a project, initializes its database, or calls providers.
"""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi import FastAPI
from backend import camera_movements, frame_composition

app=FastAPI()
frame_composition.register(app)
catalogue=next(route.endpoint() for route in app.routes if route.path=='/api/frame-presets')
data=json.dumps({'frames':catalogue,'cameras':camera_movements.catalogue()},ensure_ascii=False).replace('<','\\u003c')
html='''<!doctype html><html lang="ru"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Камера и свет · предпросмотр</title></head><body><div id="root"></div><script id="director-preview-data" type="application/json">'''+data+'''</script><script type="module" src="/src/DirectorPreview.tsx"></script></body></html>'''
(ROOT/'frontend/director-preview.html').write_text(html,encoding='utf-8')
print('Updated frontend/director-preview.html')
