"""Реестр возможностей моделей: только то, что подтверждено источником.

Факты взяты из разобранной документации провайдеров, уже лежащей в репозитории:
`docs/VIDEO_MODELS_PROMPTING_2026-10-17.md` и скиллы `skills/video-*`. Чего в
источнике нет, того профиль не объявляет: режим first/last-frame у модели без
подтверждения недоступен, и платный запрос не инициируется.

Ключ реестра — ключ `MODEL_SPECS`: так модель называется в студии. Имя задачи
провайдера (`task_type`) в профиле не меняется.
"""
from backend.director_contracts.schemas import CapabilityProfile, Mode, profile_from_catalog
from backend.model_catalog import MODEL_SPECS

# Подтверждённые факты по моделям. Каждый факт — со ссылкой на источник в репозитории.
CAPABILITY_FACTS: dict[str, dict] = {
    'kling-3.0': {
        'supports_start_frame': True,
        'supports_end_frame': True,
        'supports_sound': True,
        'supports_negative_prompt': True,
        'duration_min_sec': 3,
        'duration_max_sec': 15,
        'source': 'skills/video-kling-3-start-end-frame/SKILL.md: image_url и image_tail_url, enable_audio, 3-15 с',
    },
    'kling-3.0-omni': {
        'supports_start_frame': False,
        'supports_end_frame': False,
        'supports_sound': True,
        'duration_min_sec': 3,
        'duration_max_sec': 15,
        'source': (
            'skills/video-kling-3-omni/SKILL.md: два кадра задаются тегами @image_N в промпте, '
            'отдельных полей image_url/image_tail_url нет'
        ),
    },
    'minimax-h3': {
        'supports_start_frame': True,
        'supports_end_frame': False,
        'duration_min_sec': 5,
        'duration_max_sec': 15,
        'source': 'skills/video-minimax-h3/SKILL.md: img2video (картинка становится первым кадром), последнего кадра нет',
    },
    'seedance-2.0': {
        'supports_start_frame': True,
        'supports_end_frame': True,
        'duration_min_sec': 4,
        'duration_max_sec': 15,
        'source': 'docs/VIDEO_MODELS_PROMPTING_2026-10-17.md: режим first_last_frames, 4-15 с',
    },
    'seedance-2.5': {
        'supports_start_frame': False,
        'supports_end_frame': False,
        'duration_min_sec': 4,
        'duration_max_sec': 30,
        'source': (
            'docs/VIDEO_MODELS_PROMPTING_2026-10-17.md: режимы edit и extend, '
            'отдельного first_last_frames в источнике нет'
        ),
    },
    'hunyuan-i2v': {
        'supports_start_frame': True,
        'supports_end_frame': False,
        'source': 'backend/model_catalog.py: task_type=img2video-replace, ref_field=image — один стартовый кадр',
    },
}


def facts_for(model_id: str) -> dict:
    """Подтверждённые факты модели; пусто — если подтверждения нет."""
    return dict(CAPABILITY_FACTS.get(model_id) or {})


def profile_for(model_id: str) -> CapabilityProfile:
    """Профиль возможностей модели из каталога и подтверждённых фактов."""
    spec = MODEL_SPECS.get(model_id)
    if spec is None:
        raise KeyError(model_id)
    return profile_from_catalog(spec, facts_for(model_id), model_id=model_id)


def registry() -> list[CapabilityProfile]:
    """Профили всех моделей каталога — для интерфейса и проверок."""
    return [
        profile_from_catalog(spec, facts_for(model_id), model_id=model_id)
        for model_id, spec in MODEL_SPECS.items()
    ]


def available_modes(profile: CapabilityProfile) -> list[Mode]:
    """Режимы подачи, которые профиль подтверждает."""
    modes: list[Mode] = []
    if profile.kind == 'video':
        modes.append('text_to_video')
        if profile.supports_start_frame:
            modes.append('image_to_video')
        if profile.supports_start_frame and profile.supports_end_frame:
            modes.append('start_end_video')
    elif profile.kind == 'image':
        modes.append('text_to_image')
        if 'reference_image_edit' in profile.modes:
            modes.append('reference_image_edit')
    return modes


def mode_available(profile: CapabilityProfile, mode: Mode) -> bool:
    """Доступен ли режим подачи у этой модели."""
    return mode in available_modes(profile)
