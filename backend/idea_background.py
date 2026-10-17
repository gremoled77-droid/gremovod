"""Фоновый сценарный скилл для LLM на экране «Идея»: выжимка из skills/gremovod-screenplay, без обращения в сеть."""
import hashlib
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / 'skills' / 'gremovod-screenplay' / 'idea-background.md'
TOPICS = ['история и изменение', 'выбор героя и цена', 'финал и короткий формат', 'мир и канон', 'диалог и юмор', 'проверка идеи']


def load():
    """Текст выжимки, число символов и версия (по содержимому). Пустой файл или его отсутствие дают пустой текст."""
    try:
        text = PATH.read_text(encoding='utf-8').strip()
    except OSError:
        text = ''
    return {'text': text, 'chars': len(text), 'version': hashlib.sha256(text.encode('utf-8')).hexdigest()[:12], 'topics': TOPICS}


def register(app, studio):
    @app.get('/api/idea/background')
    def background():
        return load()
