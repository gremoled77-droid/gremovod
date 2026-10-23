"""Помощник постановки: история сообщений со ссылками на объекты и карточки следующих действий по кадру.

Ответ строится по состоянию кадра на сервере, без LLM (платный LLM на этой базе выключен). Карточки сами ничего
не запускают: интерфейс открывает нужный инструмент, а платное действие идёт через оценку цены и подтверждение.
"""
import json
import uuid

from fastapi import HTTPException
from pydantic import BaseModel, Field

HISTORY = 100
ACTIVE = {'queued', 'running', 'saving'}


class Message(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    node_id: str | None = Field(default=None, max_length=100)


def card(action, label, node_id, note='', paid=False):
    return {'action': action, 'label': label, 'node_id': node_id, 'note': note, 'paid': paid}


def suggest(ws):
    """Следующие шаги кадра по его рабочему месту (GET …/workspace)."""
    nid, files = ws['frame']['id'], ws['files']
    name = f"кадр {ws['scene']['number']}.{ws['frame']['number']}"
    video_running = any(j['kind'] == 'video' and j['status'] in ACTIVE for j in ws['jobs'])
    cards = []
    if ws['image_choice'] == 'none':
        cards.append(card('open_create', 'Сделать фото кадра', nid, f'У {name} ещё нет изображений.'))
    elif ws['image_choice'] == 'candidate':
        cards.append(card('pick_photo', 'Выбрать главное фото', nid, f'У {name} фото есть, но главное не выбрано: оживить можно только его.'))
    if video_running:
        cards.append(card('watch', 'Видео генерируется', nid, 'Статус обновится на доске сам.'))
    elif ws['image_choice'] == 'main' and ws['video_choice'] == 'none':
        cards.append(card('animate', 'Оживить кадр', nid, 'Перед запуском — оценка цены и подтверждение.', paid=True))
    elif ws['video_choice'] == 'candidate':
        cards.append(card('pick_video', 'Выбрать главное видео', nid, f'Без главного видео {name} не попадёт в выгрузку.'))
    if not ws['cues']:
        cards.append(card('open_sound', 'Добавить звук кадра', nid, 'Реплика, атмосфера или шум.'))
    if ws['video_choice'] == 'main':
        cards.append(card('export', 'Выгрузить в CapCut', nid, f'{name.capitalize()} готов к монтажу.'))
    return cards


def history(studio, pid, node_id=None):
    """Сообщения с подписями объектов, прочитанными сейчас: в истории хранятся только id."""
    with studio.connect() as db:
        rows = db.execute('SELECT * FROM assistant_messages WHERE production_id=?' + (' AND node_id=?' if node_id else '')
                          + ' ORDER BY created_at DESC,rowid DESC LIMIT ?', (pid, node_id, HISTORY) if node_id else (pid, HISTORY)).fetchall()
        titles = {}
        for row in rows:
            if row['node_id'] and row['node_id'] not in titles:
                frame = db.execute('SELECT f.title,f.number,s.number AS scene FROM production_nodes f LEFT JOIN production_nodes s ON s.id=f.parent_id WHERE f.id=?',
                                   (row['node_id'],)).fetchone()
                titles[row['node_id']] = f"Кадр {frame['scene']}.{frame['number']} · {frame['title']}" if frame else 'Кадр удалён'
    return [{'id': r['id'], 'role': r['role'], 'text': r['text'], 'node_id': r['node_id'], 'node_title': titles.get(r['node_id']),
             'cards': json.loads(r['cards']), 'created_at': r['created_at']} for r in reversed(rows)]


def register(app, studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS assistant_messages(id TEXT PRIMARY KEY, production_id TEXT NOT NULL, node_id TEXT,
                role TEXT NOT NULL, text TEXT NOT NULL, cards TEXT NOT NULL, created_at TEXT NOT NULL)''')

    def production(pid):
        with studio.connect() as db:
            if not db.execute('SELECT 1 FROM productions WHERE id=?', (pid,)).fetchone():
                raise HTTPException(404, 'Общий проект не найден')

    @app.get('/api/productions/{pid}/assistant')
    def read(pid: str, node_id: str | None = None):
        production(pid)
        return history(studio, pid, node_id)

    @app.post('/api/productions/{pid}/assistant')
    def say(pid: str, body: Message):
        production(pid)
        if body.node_id:
            # Тот же ответ, что видят инструменты (GET …/workspace): одна истина о кадре.
            from backend import production_entities
            workspace = production_entities.workspace_state(studio, pid, body.node_id)
            cards = suggest(workspace)
            reply = 'Следующие шаги по кадру:' if cards else 'По этому кадру всё готово.'
        else:
            cards = []
            reply = 'Выбери кадр на доске — предложу следующие шаги по нему.'
        with studio.connect() as db:
            for role, text, items in (('user', body.text.strip(), []), ('assistant', reply, cards)):
                db.execute('INSERT INTO assistant_messages VALUES(?,?,?,?,?,?,?)',
                           (uuid.uuid4().hex, pid, body.node_id, role, text, json.dumps(items, ensure_ascii=False), studio.now()))
        return history(studio, pid)[-2:]
