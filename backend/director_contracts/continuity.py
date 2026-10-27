"""Физическая непрерывность: opening → transition → closing.

Проверяются текстовые метаданные состояния, а не картинка: vision-QC здесь нет
и не обещается. Итоговое решение по кадру принимает человек.

Главное правило: неизменяемое по авторскому решению (геометрия кузова,
внешность, цвет) нельзя «перегенерировать» текстом. Такие свойства помечены
в `LOCKED_PREDICATES` и должны оставаться одинаковыми на всём кадре.
"""
from .schemas import LOCKED_PREDICATES, PREDICATES, ShotContract
from .validation import Issue

_KEY = 'subject_id', 'predicate'


def _key(fact) -> tuple[str, str]:
    return fact.subject_id, fact.predicate


def state_after(shot: ShotContract) -> dict[tuple[str, str], str]:
    """Состояние предметов после кадра: opening, затем применённые переходы."""
    state: dict[tuple[str, str], str] = {}
    for fact in shot.physical_state.opening:
        state[_key(fact)] = fact.value
    for fact in shot.physical_state.transitions:
        if fact.to_value is None:
            continue
        state[_key(fact)] = fact.to_value
    return state


def check_continuity(shot: ShotContract) -> list[Issue]:
    """Проверка непрерывности внутри одного кадра."""
    found: list[Issue] = []
    state = shot.physical_state

    for position, fact in enumerate(state.opening):
        if fact.predicate not in PREDICATES:
            found.append(
                Issue(
                    code='continuity_unknown_predicate',
                    severity='warning',
                    path=f'physical_state.opening[{position}].predicate',
                    message=f'Предикат {fact.predicate} не входит в реестр',
                )
            )

    for position, fact in enumerate(state.transitions):
        path = f'physical_state.transitions[{position}]'
        if fact.predicate not in PREDICATES:
            found.append(
                Issue(
                    code='continuity_unknown_predicate',
                    severity='warning',
                    path=f'{path}.predicate',
                    message=f'Предикат {fact.predicate} не входит в реестр',
                )
            )
        if fact.from_value is None and fact.to_value is None:
            found.append(
                Issue(
                    code='continuity_empty_transition',
                    path=path,
                    message='Переход не меняет состояние и ничего не описывает',
                )
            )
        if fact.from_value is not None and fact.to_value is not None:
            if not fact.event_id:
                found.append(
                    Issue(
                        code='continuity_transition_without_event',
                        path=f'{path}.event_id',
                        message='Изменение состояния должно ссылаться на событие сценария',
                    )
                )
            if fact.predicate in LOCKED_PREDICATES and fact.from_value != fact.to_value:
                found.append(
                    Issue(
                        code='continuity_locked_change',
                        path=path,
                        message=(
                            f'Свойство «{fact.predicate}» неизменяемо: '
                            f'нельзя менять {fact.from_value!r} на {fact.to_value!r}'
                        ),
                    )
                )

    # Скачок времени объявлен — состояния до и после не сравниваются.
    if state.continuity_mode in ('time_jump', 'flashback'):
        return found

    opening = {_key(fact): fact.value for fact in state.opening}
    closing = {_key(fact): fact.value for fact in state.closing}
    # Конец кадра сверяется с состоянием ПОСЛЕ переходов, а не с началом:
    # «дверь открылась в кадре» — законное изменение, а не расхождение.
    expected = state_after(shot)
    for key, value in sorted(closing.items()):
        subject, predicate = key
        if key not in expected:
            found.append(
                Issue(
                    code='continuity_undeclared_closing',
                    severity='warning',
                    path=f'physical_state.closing[{subject}.{predicate}]',
                    message=(
                        f'Состояние «{subject}.{predicate}» появляется только в конце кадра: '
                        'изменение не объявлено переходом'
                    ),
                )
            )
            continue
        if expected[key] == value:
            continue
        code = (
            'continuity_locked_change'
            if predicate in LOCKED_PREDICATES
            else 'continuity_value_mismatch'
        )
        found.append(
            Issue(
                code=code,
                path=f'physical_state.closing[{subject}.{predicate}]',
                message=(
                    f'Состояние «{subject}.{predicate}» в конце кадра '
                    f'({value!r}) не совпадает с состоянием после переходов '
                    f'({expected[key]!r})'
                ),
            )
        )
    return found


def check_chain(shots: list[ShotContract]) -> list[Issue]:
    """Непрерывность между соседними кадрами одной сцены.

    Сравнивается конец предыдущего кадра с началом следующего. Скачок времени
    внутри кадра разрывает цепочку: после него состояние может быть другим.
    """
    found: list[Issue] = []
    for position in range(1, len(shots)):
        previous = shots[position - 1]
        current = shots[position]
        if previous.scene_id != current.scene_id:
            continue
        if previous.physical_state.continuity_mode in ('time_jump', 'flashback'):
            continue
        if current.physical_state.continuity_mode in ('time_jump', 'flashback'):
            continue
        before = state_after(previous)
        after = {_key(fact): fact.value for fact in current.physical_state.opening}
        for key in sorted(set(before) & set(after)):
            subject, predicate = key
            if before[key] == after[key]:
                continue
            code = (
                'continuity_locked_change'
                if predicate in LOCKED_PREDICATES
                else 'continuity_chain_break'
            )
            found.append(
                Issue(
                    code=code,
                    path=f'shots[{position}].physical_state.opening[{subject}.{predicate}]',
                    message=(
                        f'Состояние «{subject}.{predicate}» меняется между кадрами: '
                        f'{before[key]!r} → {after[key]!r} без объявленного перехода'
                    ),
                )
            )
    return found
