"""Сценарный этап для внешнего оркестратора (n8n Cloud).

Контур нужен для одного сценарного этапа: n8n инициирует обработку, передаёт
параметры и получает результат. Вся логика этапа, состояние проекта, модельный
адаптер и учёт бюджета остаются в студии — здесь только транспорт.

Здесь только MOCK: обращения к провайдеру нет, цена 0, бюджет не тратится.
Платный запуск сценарного этапа выполняется в студии владельцем: там оценка,
подпись и резерв расходов. Запрос не может выбрать провайдера или модель —
в модели поля лишние запрещены.

Доступ:
- машинный токен студии (`Authorization: Bearer <токен>`), зона токена должна
  включать проект;
- контур включён только при `STUDIO_SCENARIO_ENABLED=1`. Без этого флага
  удалённый вызов отклоняется: согласование HTTPS-доступа — решение владельца.
"""
import os

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend import producer_stage, service_auth

ENABLE_ENV = 'STUDIO_SCENARIO_ENABLED'


class ScenarioRequest(BaseModel):
    """Параметры сценарного этапа от внешнего оркестратора.

    Провайдера и модели здесь нет: внешний вызов не решает, за чём платить.
    """

    model_config = ConfigDict(extra='forbid')
    project_id: str = Field(min_length=1, max_length=100)
    idea: str = Field(min_length=1, max_length=producer_stage.MAX_IDEA_CHARS)
    character_ids: list[str] = Field(default_factory=list, max_length=producer_stage.MAX_CHARACTERS)
    world: dict[str, str] = Field(default_factory=dict)
    duration_seconds: int = Field(default=60, ge=5, le=3600)
    language: str = Field(default='ru', min_length=2, max_length=16)
    constraints: list[str] = Field(default_factory=list, max_length=producer_stage.MAX_CONSTRAINTS)
    request_id: str = Field(default='', max_length=120, pattern=r'^[A-Za-z0-9_:-]*$')


def enabled():
    """Контур включён только явным флагом владельца."""
    return os.environ.get(ENABLE_ENV, '').strip() == '1'


def register(app, studio):
    @app.post('/api/scenario/producer')
    def producer(body: ScenarioRequest, request: Request):
        """Один сценарный этап: идея → сценарная структура. Только MOCK, стоимость 0."""
        service_auth.require_project(request, body.project_id)
        if not enabled():
            raise HTTPException(503, 'Сценарный контур не включён: нужно согласование HTTPS-доступа '
                                     f'({ENABLE_ENV}=1 и токен с зоной проекта)')
        stage_request = producer_stage.ProducerRequest(
            project_id=body.project_id,
            idea=body.idea,
            character_ids=body.character_ids,
            reference_ids=[],
            world=body.world,
            duration_seconds=body.duration_seconds,
            language=body.language,
            constraints=body.constraints,
            provider=producer_stage.MOCK_PROVIDER,
            model=producer_stage.MOCK_MODEL,
        )
        payload, summary = producer_stage.build_payload(studio, stage_request)
        messages, background = producer_stage.build_messages(payload)
        version = producer_stage.prompt_version(messages, background)
        structure = producer_stage.mock_structure(payload)
        try:
            producer_stage.check_references(structure, payload)
        except ValueError as error:
            raise HTTPException(422, 'Сценарная структура не прошла проверку: ' + str(error))
        result = producer_stage.ProducerResult(
            stage=producer_stage.STAGE_ID,
            **structure.model_dump(),
            prompt_version=version,
            model=producer_stage.mock_model_info(),
            cost_usd=0.0,
            estimated_usd=0.0,
            external_calls=0,
            payload_summary=summary,
        )
        return {
            'mode': 'MOCK',
            'status': 'MOCK_STAGE_COMPLETE',
            'paid_call_possible': False,
            'request_id': body.request_id,
            **result.model_dump(),
        }
