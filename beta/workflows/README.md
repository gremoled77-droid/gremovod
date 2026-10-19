# Экспорт BETA-001

Файл `BETA_001_Gateway_Gemini.json` — обезличенный экспорт из n8n draft `cDmIlNKvFunUqNEm`, не содержит credentials и секретов. Не считайте его сам по себе рабочей облачной установкой.

На стороне n8n настоящий workflow в папке **BETA Lab — experiments**. Платная модель Gemini Flash привязана к **n8n Gateway credits** через управляемый gateway credential, а не через личный Anthropic.

Без свежего подтверждённого текущего баланса (поля `observedGatewayBalanceUsd` и `observedBalanceTime` первой Code-ноды) запуск **намеренно завершается ошибкой до модели**. Вредную практику автоподстановки `5` из слов владельца не использовать. При повторном импорте credential будет нужно выбрать `Gateway credits` на AI-ноде (поле credentials из Git исключено).

Не пытайтесь чинить `BETA_PRE_FLIGHT_BLOCKED` удалением первой Code-ноды. Если нет доступа к балансу — не делать запрос. Не запускать каждые 10 минут по расписанию.
