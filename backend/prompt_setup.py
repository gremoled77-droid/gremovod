"""Selected production intent for the GPT prompt writer; never a generation API."""
import json
from pathlib import Path
from fastapi import HTTPException

CATALOGUE=json.loads((Path(__file__).parent/'prompt_setup_catalogue.json').read_text(encoding='utf-8'))
GROUPS={g['id']:g for g in CATALOGUE['groups']}


def normalize(value):
    if value is None:return {}
    if not isinstance(value,dict):raise HTTPException(400,'Проверь параметры стартового меню')
    for key,choice in value.items():
        if key not in GROUPS or not isinstance(choice,str) or (choice and choice not in {p['id'] for p in GROUPS[key]['options']}):
            raise HTTPException(400,'Неизвестный параметр стартового меню')
    return {g['id']:value[g['id']] for g in CATALOGUE['groups'] if value.get(g['id'])}


def context(value):
    selected=normalize(value)
    if not selected:return None
    choices=[]
    for key,choice in selected.items():
        group=GROUPS[key];preset=next(p for p in group['options'] if p['id']==choice)
        choices.append({'parameter':key,'group_title':group['title'],**preset})
    return {'version':CATALOGUE['version'],'selection':selected,'choices':choices,
            'intent':'Structured production choices for the GPT writer, not a finished generation prompt or provider parameters.',
            'instruction':'\n'.join(p['instruction'] for p in choices)+'\n'
            'Treat these as selected production intentions. Synthesize a coherent model-specific prompt, not a list of labels. '
            'Reference identity, selected framing, physical cabin layout and explicit lighting take priority over incidental stylistic effects. '
            'For an anchored video preserve the established image design rather than redesigning the first frame. '
            'Do not invent API fields, hidden quality settings, resolution, dialogue, props or unsupported controls.'}
