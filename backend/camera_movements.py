"""Original camera presets shared by the catalogue and prompt composers."""
from typing import Literal
import json
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from backend import prompt_setup

# Descriptions and schematic previews are authored for this application.
PRESETS=[
    ('static','Статичная камера','Static','Без движения','Фиксированный кадр для реплики или спокойной сцены.','Hold the camera locked in its starting position and retain the initial framing.',0,0,1,1,0),
    ('dolly-in','Наезд камеры','Dolly in','Наезд и отъезд','Камера приближается к герою; перспектива и глубина меняются.','Advance the camera toward the focal subject along a straight path, allowing natural perspective change.',0,0,1.35,1.12,0),
    ('dolly-out','Отъезд камеры','Dolly out','Наезд и отъезд','Камера удаляется и открывает окружение.','Retreat the camera from the focal subject along a straight path, gradually revealing its surroundings.',0,0,.72,.9,0),
    ('zoom-in','Оптическое приближение','Zoom in','Наезд и отъезд','Приближение объективом из одной точки; перспектива сохраняется.','Increase focal length from a fixed camera position to tighten the composition; retain perspective.',0,0,1.3,1.3,0),
    ('zoom-out','Оптическое удаление','Zoom out','Наезд и отъезд','Объектив расширяет кадр из одной точки.','Decrease focal length from a fixed camera position to widen the composition; retain perspective.',0,0,.78,.78,0),
    ('truck-left','Проезд влево','Truck left','В стороны','Камера смещается влево с заметным параллаксом.','Translate the camera left across the set, keeping its viewing direction steady and revealing depth through parallax.',25,0,1,1,0),
    ('truck-right','Проезд вправо','Truck right','В стороны','Камера смещается вправо, сохраняя направление объектива.','Translate the camera right across the set, keeping its viewing direction steady and revealing depth through parallax.',-25,0,1,1,0),
    ('pan-left','Панорама влево','Pan left','Поворот и наклон','Поворот камеры влево вокруг неподвижной опоры.','Pivot the camera left around its fixed support to reframe the scene horizontally.',32,0,1,1,0),
    ('pan-right','Панорама вправо','Pan right','Поворот и наклон','Поворот камеры вправо вокруг неподвижной опоры.','Pivot the camera right around its fixed support to reframe the scene horizontally.',-32,0,1,1,0),
    ('tilt-up','Наклон вверх','Tilt up','Поворот и наклон','Камера смотрит выше; её опора остаётся на месте.','Pivot the camera upward from its fixed support, bringing the upper part of the scene into view.',0,25,1,1,0),
    ('tilt-down','Наклон вниз','Tilt down','Поворот и наклон','Камера переводит взгляд сверху вниз.','Pivot the camera downward from its fixed support, bringing the lower part of the scene into view.',0,-25,1,1,0),
    ('pedestal-up','Подъём камеры','Pedestal up','По высоте','Вся камера поднимается, сохраняя горизонтальный взгляд.','Raise the whole camera vertically while keeping its optical axis level.',0,20,1,1,0),
    ('pedestal-down','Опускание камеры','Pedestal down','По высоте','Вся камера опускается, сохраняя направление взгляда.','Lower the whole camera vertically while keeping its optical axis level.',0,-20,1,1,0),
    ('arc-left','Дуга влево','Arc left','Обход','Небольшой обход героя слева с новым ракурсом.','Travel along a short leftward arc around the focal subject, maintaining a consistent radius and framing.',22,0,1,1,-12),
    ('arc-right','Дуга вправо','Arc right','Обход','Небольшой обход героя справа с новым ракурсом.','Travel along a short rightward arc around the focal subject, maintaining a consistent radius and framing.',-22,0,1,1,12),
    ('tracking','Следование за героем','Tracking','Следование','Камера сопровождает движение героя с постоянной дистанцией.','Track alongside the moving subject at its pace, maintaining a consistent viewing distance.',-35,0,1,1,0),
    ('handheld','Ручная камера','Handheld','Следование','Живое движение оператора с лёгкими микроколебаниями.','Use restrained handheld motion with small organic corrections while keeping the focal subject readable.',2,1,1,1,1),
    ('crane-reveal','Подъём с раскрытием','Crane reveal','По высоте','Камера поднимается и раскрывает пространство вокруг героя.','Lift the camera on an ascending path and widen the view to reveal the surrounding space.',0,18,.8,.9,0),
    ('dolly-zoom','Наезд с обратным зумом','Dolly zoom','Обход','Размер героя почти неизменен, а перспектива фона меняется.','Advance the camera while compensating with a wider lens, holding the subject size steady as background perspective shifts.',0,0,1,.76,0),
]

class Selection(BaseModel):
    preset_id:str=Field(default='',max_length=60)
    speed:Literal['slow','medium','fast']='slow'
    amplitude:Literal['small','medium','large']='small'
    note:str=Field(default='',max_length=1000)
    setup:dict[str,str]=Field(default_factory=dict)

def catalogue():
    return [{'id':p[0],'title':p[1],'english':p[2],'category':p[3],'description':p[4],
             'preview':{'x':p[6],'y':p[7],'scale':p[8],'background_scale':p[9],'rotation':p[10]}} for p in PRESETS]

def context(value):
    if not value:return None
    try:selection=Selection.model_validate(value)
    except ValidationError:raise HTTPException(400,'Проверь параметры выбранного движения камеры')
    base=prompt_setup.context(selection.setup)
    if not selection.preset_id:
        if not base:return None
        return {**payload(selection),'title':'По заданию','english':'','prompt_base':base,'instruction':'SELECTED PROMPT BASE:\n'+base['instruction']}
    preset=next((p for p in PRESETS if p[0]==selection.preset_id),None)
    if not preset:raise HTTPException(400,'Движение камеры отсутствует в каталоге')
    instruction=preset[5]
    if preset[0]!='static':
        speed={'slow':'slow and measured','medium':'moderate and even','fast':'fast and decisive'}[selection.speed]
        amount={'small':'a short travel or framing change','medium':'a moderate travel or framing change','large':'a pronounced travel or framing change'}[selection.amplitude]
        instruction+=f' Use {speed} motion with {amount}. Settle briefly into the final composition.'
    instruction+=' Use this as the single governing camera move for the shot; resolve conflicting camera instructions in the brief in its favour. Preserve the subject and scene identity.'
    if selection.note.strip():instruction+=' Camera intent: '+selection.note.strip()
    if base:instruction+='\nSELECTED PROMPT BASE:\n'+base['instruction']
    return {**payload(selection),**({'prompt_base':base} if base else {}),'title':preset[1],'english':preset[2],'instruction':instruction}

def payload(selection):
    result=selection.model_dump();result['setup']=prompt_setup.normalize(result['setup'])
    if not result['setup']:result.pop('setup')
    return result

def basis(value):
    selection=Selection.model_validate(value or {})
    return json.dumps(payload(selection),ensure_ascii=False,separators=(',',':'))

def register(app):
    @app.get('/api/camera-presets')
    def listing():return {'presets':catalogue(),'preview_type':'original_schematic','version':'2026-10-15'}
