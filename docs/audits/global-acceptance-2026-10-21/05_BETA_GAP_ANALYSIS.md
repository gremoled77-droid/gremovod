# Минимальная рабочая бета

Статус приёмки: PARTIAL. Цель — локальная студия одного владельца, способная выпустить пилот с сохранением исходников и явным разрешением каждой оплаты.

## BETA_REQUIRED

| Условие | Что уже есть | Минимальный оставшийся шаг |
|---|---|---|
| Безопасные расходы | общий ledger, quotes, idempotency, UNKNOWN | GA-01; отрицательные usage/таймауты/отсутствие usage не освобождают деньги |
| Рабочий выбранный LLM-маршрут | guarded_chat, Producer | GA-02 если task API остаётся доступным; иначе явно закрыть его до приёмки, не выдавать экран за работающий |
| Идея → утверждённый сценарий → сцены | Producer + отдельный Story Plan | один проверенный ручной перенос/preview/apply с revision; не обязательно новый автоагент |
| Канон и референсы | production character library, категории, выбор источников | владелец выбирает конкретные утверждённые IDs и права; сценарий с повторным открытием проекта |
| Раскадровка → материалы | jobs, outputs, library, delivery | один офлайн E2E с временными файлами и mock dispatcher, затем отдельный разрешённый live smoke |
| Звук → монтаж | voice profiles, cue sheet, upload, CSV edit-list | настоящие реплики/синхронность и ручной CapCut import/render; не строить новый NLE |
| Проверенный master | import MP4, N34, N35, отдельный QA | GA-03 и ручное решение владельца для того же SHA |
| Сохранность | SQLite transactions, revisions, cleanup protections | восстановление копии одного пилотного проекта и сверка хэшей исходников |
| Проверяемый кандидат | офлайн тесты текущего аудита | GA-04 CI; зафиксировать SHA, исключить недописанные локальные правки |

Источники: [backend/producer_stage.py:175](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/producer_stage.py#L175), [backend/story_plan.py:168](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/story_plan.py#L168), [backend/main.py:538](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L538), [backend/edit_list.py:160](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/edit_list.py#L160), [backend/media_qc.py:1](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/media_qc.py#L1), [backend/qa_reviews.py:46](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/qa_reviews.py#L46).

## Проход от начала до конца

1. Создать временный project/production, выбрать канонические reference IDs. Roundtrip API прошёл; browser **NOT_RUN**.
2. Ввести brief, получить mock Producer structure, сохранить `state.scenario`. Это проверенный MOCK, не результат paid LLM.
3. Перенести выбранные сцены в отдельный Story Plan, preview/apply. Сам apply проверен; сквозной перенос Producer → план не доказан. Ручной путь допустим для первой беты.
4. Составить storyboard, выбрать образы, shot/camera/light; ввести редактируемый prompt. Отдельные validators/roundtrips прошли.
5. Оценить конкретную генерацию, подтвердить запрос и цену, отправить один раз. В аудите provider был заменён mock. Реальный live вызов **NOT_RUN** по прямому запрету.
6. Доставить output в library, привязать к нужному shot, повторно открыть проект. Mock delivery и синтетический MP4 проверены.
7. Подготовить голос/cue sheet; TTS smoke **NOT_RUN**, локальный import/analyze/cut прошёл на временном WAV.
8. Получить edit-list CSV и по нему собрать CapCut-проект; импорт и ручной render **NOT_RUN**. CSV не равен редактируемому проекту CapCut или архиву со всеми файлами.
9. Импортировать master с актуальной revision; выполнить N34, freeze/evidence N35, художественный просмотр владельца. Модули прошли отдельно на синтетическом MP4, единый выпуск **NOT_RUN**; `ready` импорта не является подтверждением этого шага.
10. Сохранить финальный SHA, approvals и исходники. Публикация на площадках вне аудита.

## AFTER_BETA

Автоматический Producer → Story Plan adapter (если ручной перенос достаточен), полный n8n saved-agent cycle, helper/multi-user UI, коммерческие квоты клиентов, автоматический рендер вне CapCut, optional beat lint и ссылки Shorts, дополнительная оптимизация bundle.

Удалённый доступ: GA-05 обязателен **перед его использованием**; локальный пилот может оставаться loopback. Не превращать публичный SaaS/все модели/всех критиков в обязательное условие выпуска пилота.

## RESEARCH_ONLY

PR #50 AI-editor prompt, #51 «сцепка», #52 business essays/канал и #53 Gemini case — источники предложений. Универсальные 8-секундные биты, автоматическая вырезка постановочных пауз, три обязательных LLM-критика для каждого черновика и чужие художественные примеры не утверждены.

## Конкретные блокировки проверки

Нет **выбранного для этого аудита** настоящего MP4 пилота, подтверждённого канон-snapshot и решения владельца по конкретной финальной версии; это не заявление об отсутствии таких файлов на диске. Windows доступен, FFmpeg работает. API credentials/production SQLite не читались. Платные вызовы запрещены заданием. Эти условия нельзя заменить зелёными mock-тестами.
