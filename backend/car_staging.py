"""Original GremoVOD staging recipes. Vehicle sides are never screen sides."""
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field


class CarStaging(BaseModel):
    shot_id: str = Field(default='', max_length=60)
    steering: Literal['reference', 'left', 'right'] = 'reference'
    guest_seat: Literal['front', 'rear-left', 'rear-center', 'rear-right'] = 'rear-right'
    vehicle_state: Literal['parked', 'moving'] = 'moving'
    light_id: Literal['', 'day', 'overcast', 'night', 'rain'] = ''


# id, title, description, physical camera station, target seat, allowed guest rows, complexity, instruction
SHOTS = [
    ('car-front-two', 'Двое спереди', 'Общий разговор и совместная реакция.', 'dash-center', 'both', 'front', False,
     'From the central windshield/dashboard area looking inward, frame the driver and front guest together. Use moderate width without stretching faces.'),
    ('car-driver-three-quarter', 'Грэм · три четверти', 'Основная реплика водителя, часть руля в кадре.', 'dash-center', 'driver', 'any', False,
     'From the center dashboard area, aim toward the driver in a medium three-quarter view. Retain a plausible part of the existing steering wheel and side window.'),
    ('car-front-guest-three-quarter', 'Гость спереди', 'Отдельный план переднего пассажира.', 'dash-center', 'guest', 'front', False,
     'From the center dashboard area, aim toward the front passenger in a medium three-quarter view. This is a distinct camera angle, never a mirrored driver shot.'),
    ('car-rear-guest', 'Гость сзади', 'Основной ответ заднего пассажира.', 'front-center', 'guest', 'rear', False,
     'From the front-seat area looking backward, frame the rear guest at the exact assigned seat in a medium view. Retain the correct headrests and window line.'),
    ('car-driver-reverse', 'Грэм · обратный план', 'Косой профиль водителя с заднего ряда.', 'rear-center', 'driver', 'any', False,
     'From the rear row between the seats, frame the driver in an oblique profile. Preserve the driver seat, shoulder and recognizable identity.'),
    ('car-rear-guest-ots', 'Гость через плечо', 'Связь собеседников через плечо водителя.', 'driver-shoulder', 'guest', 'rear', False,
     'From just behind the existing driver shoulder, look toward the assigned rear guest, only if physically possible in the reference cabin. Do not add a foreground person or seat.'),
    ('car-rear-forward', 'Сзади на дорогу', 'Установочный план: водитель, салон и дорога.', 'rear-center', 'road', 'any', False,
     'From the rear row looking forward, show the existing front seats, driver and road. Show a front guest only when that seat is occupied. This is not a face shot of a rear guest.'),
    ('car-driver-side', 'Профиль Грэма', 'Внутренняя камера сбоку от водителя.', 'front-passenger-side', 'driver', 'any', False,
     'Place a small interior camera on the passenger side aimed across at the driver profile; avoid obstructing eyes with the pillar or occupying the guest body.'),
    ('car-guest-window', 'Гость у окна', 'Три четверти пассажира, окно на фоне.', 'center-near-guest', 'guest', 'any', False,
     'From the cabin center near the assigned guest row, frame the guest in three-quarter view with the corresponding side window behind. Preserve the exact seat; reflections must not obscure identity.'),
    ('car-mirror-eyes', 'Глаза в зеркале', 'Короткий акцент. Сложное отражение.', 'mirror-view', 'mirror', 'any', True,
     'Show only one physically correct reflection of the driver eyes in the existing interior mirror. Do not duplicate faces or use this as the main identity reference.'),
    ('car-windshield', 'Через лобовое стекло', 'Внешняя камера смотрит в салон.', 'outside-front', 'both', 'any', True,
     'Place the camera OUTSIDE the car in front of the windshield, looking into the cabin. Preserve assigned seats, glass, wipers and plausible reflections; never move a rear guest forward to include them.'),
    ('car-detail', 'Деталь действия', 'Рука на руле или существующие приборы.', 'dash-center', 'detail', 'any', False,
     'Frame ONE existing action detail, such as the driver hand on the steering wheel or an existing dashboard detail. Do not invent phones, meters, logos or extra hands.'),
]

LIGHTS = [
    ('day', 'Дневной разговор', 'Мягкий свет окон, естественные лица.', 'Use broad soft daylight through the existing windows, readable eyes and dimensional shadows.'),
    ('overcast', 'Пасмурный Минск', 'Прохладный рассеянный день.', 'Use cool diffuse overcast daylight, restrained contrast and readable faces. Keep the same time of day.'),
    ('night', 'Ночное такси', 'Тёплая улица и прохладное окружение.', 'Use restrained warm street light with cooler night ambience and weak dashboard fill from below. Preserve natural facial color; the dashboard is not the main light.'),
    ('rain', 'Ночь и дождь', 'Лицо в фокусе, капли снаружи стекла.', 'Use night street lighting and rain drops on the OUTSIDE of the windows. Focus on the face; keep reflections subordinate and do not duplicate faces.'),
]


def catalogue():
    return {
        'car_shots': [dict(zip(('id', 'title', 'description', 'station', 'target', 'guest_row', 'complex'), shot[:7])) for shot in SHOTS],
        'car_lights': [{'id':p[0], 'title':p[1], 'description':p[2]} for p in LIGHTS],
    }


def instructions(car: CarStaging):
    shot = next((p for p in SHOTS if p[0] == car.shot_id), None)
    if car.shot_id and not shot:
        raise HTTPException(400, 'Автомобильный ракурс отсутствует в каталоге')
    row = 'front' if car.guest_seat == 'front' else 'rear'
    if shot and shot[5] not in ('any', row):
        raise HTTPException(400, 'Этот ракурс не подходит к выбранному месту гостя')
    if shot and shot[0] == 'car-guest-window' and car.guest_seat == 'rear-center':
        raise HTTPException(400, 'Для плана у окна выбери боковое место гостя')
    steering = {'reference':'Use the steering-wheel side from the approved car reference; do not guess or mirror it.',
                'left':'The steering wheel and driver are on the VEHICLE LEFT.',
                'right':'The steering wheel and driver are on the VEHICLE RIGHT.'}[car.steering]
    guest = {'front':'the front passenger seat, opposite the driver', 'rear-left':'the VEHICLE LEFT rear seat',
             'rear-center':'the center rear seat', 'rear-right':'the VEHICLE RIGHT rear seat'}[car.guest_seat]
    result = [
        'CAR STAGING: '+steering+' Grem is the existing driver. The existing guest stays in '+guest+'. No other occupants.',
        'Vehicle sides are measured facing the direction of travel, independently of screen-left and screen-right. Preserve the approved cabin reference: wheel, dashboard, mirror, pillars, windows, seats, headrests and belts. Do not mirror the cabin or swap characters between seats.',
        'The vehicle is '+('moving; the driver looks predominantly at the road, with only brief motivated glances.' if car.vehicle_state=='moving' else 'parked; retain the stationary environment.'),
    ]
    if shot:
        result.append('CAR SHOT: '+shot[7])
    if car.light_id:
        result.append('CAR LIGHTING: '+next(p[3] for p in LIGHTS if p[0]==car.light_id))
    result.append('Across shots preserve identity, costume, seating, gaze axis, cabin geometry, time of day, weather and the physical world-space light direction. Reversing the camera does not move the light to another window. Use the approved references for all visible people and the cabin. Do not invent missing reference details.')
    return result
