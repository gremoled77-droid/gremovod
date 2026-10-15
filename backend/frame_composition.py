"""Still-frame camera positions and lighting, expressed as model-neutral instructions."""
import json
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from backend import car_staging
from backend import prompt_setup

FRAMES=[
 ('establishing','Дальний общий','Establishing shot','Масштаб','Герой небольшой, основное место занимает локация.','Use a distant establishing view with the existing subject small within the environment; keep spatial relationships legible.',.47,160,99,0,'front'),
 ('full-body','Полный рост','Full shot','Масштаб','Весь персонаж от головы до обуви с небольшими полями.','Frame the complete subject from head to feet at eye level with comfortable margins; keep body proportions natural.',.95,160,54,0,'front'),
 ('medium','Средний план','Medium shot','Масштаб','Персонаж примерно по пояс: жесты и окружение.','Use an eye-level waist-up medium shot, leaving room for the subject’s existing gesture.',1.45,160,49,0,'front'),
 ('medium-close','Погрудный','Medium close-up','Масштаб','Плечи и грудь, лицо становится главным акцентом.','Compose a chest-up medium close-up at eye level, with a small amount of headroom.',1.85,160,42,0,'front'),
 ('close-up','Крупный портрет','Close-up','Масштаб','Лицо и верх плеч для эмоции или реплики.','Use a close-up of the face with the upper shoulders at the edge of frame; preserve facial proportions and identity.',2.6,160,34,0,'front'),
 ('extreme-close','Деталь лица','Extreme close-up','Масштаб','Очень тесный кадр существующей детали: глаза или лица.','Use an extreme close-up of an existing facial detail such as the eyes; retain its original anatomy and texture.',4.8,160,5,0,'front'),
 ('three-quarter','Ракурс три четверти','Three-quarter view','Ракурс','Камера примерно в 45° к направлению лица.','Place the camera at eye level approximately 45 degrees around the subject, showing a three-quarter view while preserving identity.',1.45,160,49,0,'quarter'),
 ('profile','Профиль','Profile','Ракурс','Камера сбоку, читается силуэт лица.','Use a side-on eye-level profile view of the existing subject; retain the recognizable nose, chin and head shape.',1.85,160,42,0,'profile'),
 ('over-shoulder','Через плечо','Over the shoulder','Диалог','Плечо существующего участника на переднем плане.','Use an over-the-shoulder view only when the brief already contains a foreground participant and a target. Preserve screen direction. If no second participant exists, use the existing subject’s shoulder to frame the existing scene; do not invent another person.',1.3,205,53,0,'shoulder'),
 ('pov','От первого лица','Point of view','Диалог','Камера занимает место героя и смотрит на сцену его глазами.','Place the camera at the existing viewpoint character’s eye position, looking toward the subject or area named in the brief. Do not add a visible observer, hands or props unless requested.',1,160,55,0,'pov'),
 ('low-angle','Нижний ракурс','Low angle','Высота','Камера ниже героя и смотрит вверх; герой выглядит значительнее.','Place the camera below the subject’s eye line and angle it upward, retaining plausible anatomy and perspective.',1.05,160,55,0,'low'),
 ('high-angle','Верхний ракурс','High angle','Высота','Камера выше героя и смотрит вниз.','Place the camera above the subject and look down at a moderate angle; preserve the subject’s proportions within that perspective.',.87,160,63,0,'high'),
 ('top-down','Строго сверху','Top-down','Высота','Камера смотрит вертикально вниз; важна геометрия расположения.','Use a vertically downward top-down view of the existing arrangement. Preserve positions and spatial relationships, adapting visible surfaces naturally.',.8,160,93,0,'top'),
 ('dutch','Наклонённый горизонт','Dutch angle','Композиция','Наклон камеры вокруг оптической оси создаёт напряжение.','Use a controlled camera roll of about 15 degrees so the horizon is diagonal; keep the subject upright in the scene and preserve anatomy.',1,160,54,-15,'front'),
 ('thirds','Трети и свободное место','Rule of thirds','Композиция','Герой на трети кадра, пространство оставлено по направлению взгляда.','Place the focal subject on a vertical third with deliberate negative space toward their gaze or action; retain a balanced environment.',1,107,54,0,'quarter'),
]
LIGHTS=[
 ('soft-window','Мягкий свет из окна','Широкий источник сбоку, плавные тени.','Use broad diffused window-like side light with gentle shadow transitions and restrained fill.','left'),
 ('rembrandt','Рембрандт 45°','Объём лица и небольшой световой треугольник на теневой щеке.','Use a key about 45 degrees to one side and slightly above eye level, with restrained fill and a natural small lit area on the shadow-side cheek.','left'),
 ('split','Боковой 90°','Свет и тень делят объём лица на две стороны.','Use a lateral key at about 90 degrees with limited fill, creating a clear division between the lit and shaded sides.','right'),
 ('butterfly','Фронтальный сверху','Симметричный портретный свет с тенью под носом.','Use a centered key above the camera axis, creating balanced facial illumination and a small shadow under the nose.','front'),
 ('rim','Контровой','Свет отделяет контур героя от фона.','Use a rear key to outline the subject, adding enough soft front fill to retain identity and readable detail.','back'),
 ('overcast','Пасмурный дневной','Ровное мягкое освещение с открытым окружением.','Use broad overcast daylight with soft open shadows and natural scene color.','top'),
 ('hard-sun','Жёсткий солнечный','Направленный свет и отчётливые тени.','Use directional hard sunlight with crisp, geometrically consistent shadows and controlled highlights.','right'),
 ('warm-cool','Тёплый ключ и холодное заполнение','Тёплое лицо, прохладные тени и окружение.','Use a warm key from one side and cooler restrained ambient fill; keep the color separation plausible and skin readable.','left'),
]

class Selection(BaseModel):
    frame_id:str=Field(default='',max_length=60)
    lighting_id:str=Field(default='',max_length=60)
    direction:Literal['preset','left','right','front','back','top']='preset'
    softness:Literal['preset','soft','hard']='preset'
    temperature:Literal['preset','neutral','warm','cool']='preset'
    note:str=Field(default='',max_length=1000)
    shot_size:Literal['','establishing','full-body','medium','medium-close','close-up','extreme-close']=''
    car:car_staging.CarStaging|None=None
    setup:dict[str,str]=Field(default_factory=dict)

def selection(value):
    try:return Selection.model_validate(value or {})
    except ValidationError:raise HTTPException(400,'Проверь положение камеры и настройки света')

def payload(selected):
    result=selected.model_dump()
    # Preserve signatures of existing projects when the new controls are unused.
    if not result['shot_size']:result.pop('shot_size')
    if result['car'] is None:result.pop('car')
    result['setup']=prompt_setup.normalize(result['setup'])
    if not result['setup']:result.pop('setup')
    return result

def basis(value):return json.dumps(payload(selection(value)),ensure_ascii=False,separators=(',',':'))

def context(value):
    selected=selection(value);frame=next((p for p in FRAMES if p[0]==selected.frame_id),None);light=next((p for p in LIGHTS if p[0]==selected.lighting_id),None)
    if selected.frame_id and not frame:raise HTTPException(400,'Ракурс отсутствует в каталоге')
    if selected.lighting_id and not light:raise HTTPException(400,'Световая схема отсутствует в каталоге')
    base=prompt_setup.context(selected.setup)
    if not selected.frame_id and not selected.lighting_id and selected.direction==selected.softness==selected.temperature=='preset' and not selected.note.strip() and not selected.shot_size and selected.car is None and base is None:return None
    instructions=[]
    if base:instructions.append('SELECTED PROMPT BASE:\n'+base['instruction'])
    if selected.car and selected.car.shot_id and frame:raise HTTPException(400,'Выбери общий ракурс или автомобильный, а не оба одновременно')
    if selected.car and selected.car.light_id and light:raise HTTPException(400,'Выбери общую световую схему или режим света салона')
    if selected.car and selected.shot_size:
        car_shot=next((p for p in car_staging.SHOTS if p[0]==selected.car.shot_id),None)
        if car_shot and car_shot[4] not in ('driver','guest'):raise HTTPException(400,'Для общего плана, дороги, зеркала и детали крупность задаётся автомобильным пресетом')
    if frame:instructions.append('COMPOSITION: '+frame[5])
    if selected.shot_size:
        crop={'establishing':'a distant establishing view, with the focal subject small in the environment',
              'full-body':'the entire existing body from head to feet, if visible from the chosen camera station; never remove cabin geometry to expose a seated body',
              'medium':'a waist-up medium shot', 'medium-close':'a chest-up medium close-up',
              'close-up':'a face close-up including the upper shoulders', 'extreme-close':'one existing facial detail such as the eyes'}[selected.shot_size]
        instructions.append('SHOT SIZE: '+crop+'. This explicit crop overrides any generic crop in the composition recipe; keep the selected angle, height and physical station. For a multi-person or environment shot, crop around its named subjects rather than silently dropping a participant.')
    if selected.car:instructions.extend(car_staging.instructions(selected.car))
    if light:instructions.append('LIGHTING: '+light[3])
    if selected.direction!='preset':
        direction={'left':'camera-left','right':'camera-right','front':'near the camera axis','back':'behind the subject','top':'above the subject'}[selected.direction]
        instructions.append('Explicit key-light direction: '+direction+'. Adapt the selected lighting mood to this direction rather than forcing an incompatible shadow pattern.')
    if selected.softness!='preset':instructions.append('Explicit shadow quality: '+{'soft':'soft transitions from a broad diffused source.','hard':'crisp edges from a small directional source.'}[selected.softness])
    if selected.temperature!='preset':instructions.append('Explicit overall light temperature: '+{'neutral':'neutral, with natural subject colors.','warm':'warm, while retaining recognizable subject colors.','cool':'cool, while retaining recognizable subject colors.'}[selected.temperature])
    if selected.note.strip():instructions.append('Frame intent: '+selected.note.strip())
    instructions.append('Apply this framing and light to the existing subject and scene. Preserve identity, wardrobe and scene layout from the references; do not add people, equipment, windows or objects merely to match the schematic sample. Resolve conflicting generic camera or light defaults in favour of these selections. Produce one still image with no camera motion.')
    return {**payload(selected),**({'prompt_base':base} if base else {}),'frame_title':frame[1] if frame else '', 'lighting_title':light[1] if light else '', 'instruction':'\n'.join(instructions)}

def register(app):
    @app.get('/api/frame-presets')
    def listing():return {'frames':[{'id':p[0],'title':p[1],'english':p[2],'category':p[3],'description':p[4],'preview':{'scale':p[6],'x':p[7],'y':p[8],'rotation':p[9],'view':p[10]}} for p in FRAMES],
                          'lights':[{'id':p[0],'title':p[1],'description':p[2],'direction':p[4]} for p in LIGHTS],**car_staging.catalogue(),'capabilities':{'independent_shot_size':True,'car_staging':True,'prompt_setup':True},'preview_type':'original_schematic','version':'2026-10-15-start-menu'}
