# KIE API для Codex

Доступ к аккаунту проверен 15 октября 2026 через API баланса, включая повторную проверку с сохранённым DPAPI-ключом. Баланс на момент проверки: 80 кредитов. Генерация не запускалась.

Создайте ключ на https://kie.ai/api-key и запустите в терминале рабочего пространства:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\kie-access\connect.ps1
```

Вставьте ключ в скрытое поле терминала. Не отправляйте его в чат. После успешного GET баланса скрипт сохранит ключ, зашифрованный Windows DPAPI для текущего пользователя. Файл исключён из Git.

Проверка подключения и баланс:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\kie-access\kie.ps1 check
powershell -NoProfile -ExecutionPolicy Bypass -File .\kie-access\kie.ps1 credits
```

Wrapper также принимает KIE_API_KEY из окружения процесса. DPAPI требует того же Windows-пользователя, который сохранил ключ. Если Codex sandbox не может его расшифровать, вызывайте wrapper через разрешённый exec_command с sandbox_permissions=require_escalated в контексте этого пользователя. Не выводите расшифрованный ключ и не переносите его в открытый файл.

Используется Authorization: Bearer и GET https://api.kie.ai/api/v1/chat/credit. Проверяется также поле code: KIE может вернуть ошибку внутри HTTP 200. Генерация не запускается. Проверка баланса не подтверждает доступ к каждой модели. Параметры моделей и цены проверяйте перед генерацией.

Официальные источники:
- https://docs.kie.ai/
- https://docs.kie.ai/common-api/get-account-credits
- https://kie.ai/market
- https://kie.ai/pricing
