"""P0-контракты режиссура: события сценария, физические факты, карточки кадра.

Модуль чистый: только схемы Pydantic, без сети, без БД и без платных вызовов.
Имена полей согласованы с текущими моделями репозитория (`production_nodes`,
`production_files`, `production_entity_state`); здесь они описаны как контракты,
которые инкремент №2 свяжет с существующим storyboard.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# --- Словарь предикатов -------------------------------------------------------
# Список закрыт на уровне модели, но расширяем миграцией/регистром.
PREDICATES: dict[str, str] = {
    'vehicle_pose': 'положение автомобиля',
    'door_state': 'состояние двери',
    'vehicle_geometry': 'геометрия кузова',
    'vehicle_color': 'цвет кузова',
    'interior_exterior': 'внутри/снаружи',
    'character_pose': 'поза персонажа',
    'character_location': 'где персонаж',
    'character_outfit': 'одежда персонажа',
    'character_appearance': 'внешность персонажа',
    'prop_held': 'что в руках',
    'prop_contact': 'с кем или чем контакт',
    'camera_position': 'позиция камеры',
    'camera_framing': 'кадр в кадре',
}

# Неизменяемые по авторскому решению факты. Перегенерировать их текстом
# как «альтернативную геометрию» нельзя — нужны утверждённые ассеты.
LOCKED_PREDICATES: frozenset[str] = frozenset(
    {'vehicle_geometry', 'character_appearance', 'vehicle_color', 'character_outfit'}
)

EventKind = Literal['mandatory_action', 'dialogue', 'reveal', 'transition', 'flashback']
ContinuityMode = Literal['continuous', 'time_jump', 'flashback']
NarrativeRole = Literal['setup', 'reveal', 'reaction', 'transition', 'climax', 'closing']
ShotStatus = Literal['draft', 'proposed', 'approved']
Mode = Literal[
    'text_to_image',
    'reference_image_edit',
    'text_to_video',
    'image_to_video',
    'start_end_video',
    'video_extend',
    'audio',
]


class SourceEvent(BaseModel):
    """Событие сценария в авторской формулировке."""

    model_config = ConfigDict(extra='forbid')

    event_id: str = Field(min_length=1, max_length=64)
    episode_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=2000)
    kind: EventKind = 'mandatory_action'
    locked: bool = True
    causal_after: list[str] = Field(default_factory=list, max_length=32)
    presentation_order: int = Field(ge=0, le=10000)
    timeline_order: int = Field(ge=0, le=10000)
    assigned_shot_ids: list[str] = Field(default_factory=list, max_length=32)
    # Мотив, который допустимо показать повторно (в отличие от locked-события).
    repeatable: bool = False


class PhysicalFact(BaseModel):
    """Один проверяемый факт о состоянии предмета, а не абзац текста."""

    model_config = ConfigDict(extra='forbid')

    subject_id: str = Field(min_length=1, max_length=64)
    predicate: str = Field(min_length=1, max_length=64)
    value: str = Field(default='', max_length=200)
    from_value: str | None = Field(default=None, max_length=200)
    to_value: str | None = Field(default=None, max_length=200)
    action: str = Field(default='', max_length=300)
    event_id: str | None = Field(default=None, max_length=64)


class PhysicalState(BaseModel):
    """Состояние предметов внутри кадра: начало → переходы → конец."""

    model_config = ConfigDict(extra='forbid')

    continuity_mode: ContinuityMode = 'continuous'
    opening: list[PhysicalFact] = Field(default_factory=list, max_length=100)
    transitions: list[PhysicalFact] = Field(default_factory=list, max_length=100)
    closing: list[PhysicalFact] = Field(default_factory=list, max_length=100)


class CameraPlan(BaseModel):
    """Постановка камеры. Допускаются разные системы координат."""

    model_config = ConfigDict(extra='forbid')

    framing: str = Field(default='', max_length=80)
    movement: str = Field(default='', max_length=80)
    direction: str = Field(default='', max_length=80)
    coordinate_space: Literal['actor_world', 'camera_world'] = 'actor_world'


class ShotContract(BaseModel):
    """Режиссёрская карточка кадра."""

    model_config = ConfigDict(extra='forbid')

    shot_id: str = Field(min_length=1, max_length=64)
    scene_id: str = Field(min_length=1, max_length=64)
    source_event_ids: list[str] = Field(default_factory=list, max_length=32)
    duration_sec: float = Field(gt=0, le=120)
    narrative_role: NarrativeRole = 'setup'
    character_ids: list[str] = Field(default_factory=list, max_length=32)
    # ID уже существующей библиотеки ассетов, не ссылки и не секреты.
    asset_reference_ids: list[str] = Field(default_factory=list, max_length=32)
    camera: CameraPlan = Field(default_factory=CameraPlan)
    physical_state: PhysicalState = Field(default_factory=PhysicalState)
    author_lock_version: int = Field(ge=0, le=100000)
    status: ShotStatus = 'draft'
    # Пунктичные пути полей, которые нельзя менять предложением агента.
    locked_paths: list[str] = Field(default_factory=list, max_length=64)


class TimeJump(BaseModel):
    """Явный скачок во времени между соседними событиями по хронологии."""

    model_config = ConfigDict(extra='forbid')

    before_event_id: str = Field(min_length=1, max_length=64)
    after_event_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(default='', max_length=300)


class FilmOrder(BaseModel):
    """Порядок показа и хронологический порядок — раздельно.

    Нелинейный показ допустим: расхождение порядков не является ошибкой
    контракта, если переход времени объявлен явно.
    """

    model_config = ConfigDict(extra='forbid')

    presentation: list[str] = Field(default_factory=list, max_length=200)
    timeline: list[str] = Field(default_factory=list, max_length=200)
    time_jumps: list[TimeJump] = Field(default_factory=list, max_length=100)


class CapabilityProfile(BaseModel):
    """Проверяемые возможности конкретного endpoint провайдера.

    Отсутствие подтверждённых данных означает UNVERIFIED/BLOCKED: приблизительная
    цена или лимит не выдаются за доказанные.
    """

    model_config = ConfigDict(extra='forbid')

    model_id: str = Field(min_length=1, max_length=64)
    provider: str = Field(min_length=1, max_length=64)
    kind: Literal['image', 'video', 'audio', 'llm']
    modes: list[Mode] = Field(default_factory=list, max_length=8)
    duration_min_sec: float | None = Field(default=None, gt=0)
    duration_max_sec: float | None = Field(default=None, gt=0)
    fps: list[int] = Field(default_factory=list, max_length=8)
    aspect_ratio: list[str] = Field(default_factory=list, max_length=16)
    resolution: list[str] = Field(default_factory=list, max_length=16)
    reference_roles: list[str] = Field(default_factory=list, max_length=16)
    max_images: int = Field(default=0, ge=0, le=64)
    max_video_refs: int = Field(default=0, ge=0, le=64)
    supports_start_frame: bool = False
    supports_end_frame: bool = False
    supports_sound: bool = False
    supports_negative_prompt: bool = False
    accepted_fields: list[str] = Field(default_factory=list, max_length=64)
    price_source: str = Field(default='', max_length=200)
    price_verified_at: str = Field(default='', max_length=40)
    capability_source: str = Field(default='', max_length=400)
    launch_enabled: bool = False
    approval_gate: Literal['required', 'not_required'] = 'required'
    verified: bool = False

    @property
    def state(self) -> str:
        """UNVERIFIED — профиль не подтверждён живым вызовом; BLOCKED — запускать нельзя."""
        if not self.verified:
            return 'UNVERIFIED'
        if not self.launch_enabled:
            return 'BLOCKED'
        return 'READY'


def profile_from_catalog(
    spec: dict, facts: dict | None = None, model_id: str | None = None
) -> CapabilityProfile:
    """Собирает профиль возможностей из существующего MODEL_SPECS.

    Чего в каталоге нет, того профиль не выдумывает: неизвестные поля остаются
    пустыми, а профиль помечается как неподтверждённый. Подтверждённые факты
    (first/last frame, звук, лимиты длины) приходят отдельным словарём `facts` —
    их источник обязателен, иначе профиль остаётся неподтверждённым.
    """
    facts = facts or {}
    model_id = model_id or spec.get('task_type') or spec.get('model') or 'unknown'
    kind = 'video' if spec.get('kind') == 'video' else 'image' if spec.get('kind') == 'image' else 'llm'
    modes: list[Mode] = []
    if kind == 'image':
        modes.append('reference_image_edit' if spec.get('api_refs') else 'text_to_image')
    elif kind == 'video':
        modes.append('image_to_video' if spec.get('max_refs') else 'text_to_video')
    duration_min = spec.get('duration_min')
    duration_max = spec.get('duration_max')
    if kind == 'video' and duration_max is None:
        options = spec.get('options') or {}
        rule = options.get('duration') or {}
        duration_min = rule.get('min')
        duration_max = rule.get('max')
    if duration_min is None:
        duration_min = facts.get('duration_min_sec')
    if duration_max is None:
        duration_max = facts.get('duration_max_sec')
    verified_at = str(spec.get('verified_at') or '')
    launch_enabled = bool(spec.get('launch_enabled'))
    return CapabilityProfile(
        model_id=model_id,
        provider='piapi',
        kind=kind,
        modes=modes,
        duration_min_sec=float(duration_min) if duration_min else None,
        duration_max_sec=float(duration_max) if duration_max else None,
        aspect_ratio=[str(v) for v in (spec.get('aspect_ratio') or [])],
        resolution=[str(v) for v in (spec.get('resolution') or [])],
        reference_roles=[],
        max_images=int(spec.get('api_refs', spec.get('max_refs', 0)) or 0),
        max_video_refs=int(spec.get('max_refs', 0) or 0) if kind == 'video' else 0,
        supports_start_frame=bool(facts.get('supports_start_frame')),
        supports_end_frame=bool(facts.get('supports_end_frame')),
        supports_sound=bool(facts.get('supports_sound')),
        supports_negative_prompt=bool(facts.get('supports_negative_prompt')),
        accepted_fields=sorted((spec.get('options') or {}).keys()),
        price_source=str(spec.get('docs') or ''),
        price_verified_at=verified_at,
        capability_source=str(facts.get('source') or ''),
        launch_enabled=launch_enabled,
        approval_gate='required',
        verified=bool(verified_at) and not spec.get('prompt_only', False),
    )
