# R2: материалы сайта и приёмочные файлы

Дата: 2026-10-20. Бакет создан в аккаунте, где живёт домен `grem.win`
(`ef17029ad0904b99873cc44576f28795`).

| Что | Значение |
|---|---|
| Бакет | `gremovod` |
| S3-эндпоинт | `https://ef17029ad0904b99873cc44576f28795.r2.cloudflarestorage.com/gremovod` |
| Публичный домен | `https://assets.grem.win` |
| Dev-адрес | `https://pub-efdcc7b1ab804e3b8e1d2f3464a3cc65.r2.dev` |
| Публичный доступ | включён (r2.dev + кастомный домен) |
| Объектов | 50, 67,0 МБ, префикс `site/` |

Манифест с sha256 и content-type каждого объекта: `docs/r2/site-assets-manifest-2026-10-20.json`.

## Что важно знать про S3-API R2

- **S3-эндпоинт требует подписи на каждом запросе.** Даже для открытого бакета неподписанный GET
  возвращает 400, а не содержимое. Поэтому публичные объекты читаются через домен бакета
  (`R2_PUBLIC_BASE_URL`), а не через S3-путь.
- Для **записи** (новые файлы из студии) нужны ключи R2: `R2_ACCESS_KEY_ID` и `R2_SECRET_ACCESS_KEY`
  с правами Object Read & Write. Короткоживущие ключи выпускаются через
  `cf r2 temporary-credentials create --bucket <бакет> --permission object-read-write`, но для них
  нужен родительский R2 API-токен.
- Управление бакетами (создать, домены, публичный доступ) — через `cf` CLI или дашборд;
  коннектор Cloudflare в этой сессии пропускает только чтение.

## Как перезалить

```powershell
$env:R2_ENDPOINT='https://ef17029ad0904b99873cc44576f28795.r2.cloudflarestorage.com'
$env:R2_BUCKET='gremovod'
$env:R2_ACCESS_KEY_ID='...'; $env:R2_SECRET_ACCESS_KEY='...'
$env:R2_PUBLIC_BASE_URL='https://assets.grem.win'
cd C:\Users\BLOWKA\Documents\Minimax\_wt\gremovod-money
& C:\Users\BLOWKA\Documents\Minimax\.venv-audit\Scripts\python.exe -X utf8 -m scripts.r2_upload `
  --source C:\Users\BLOWKA\Documents\Minimax\gremovod-site-assets --prefix site `
  --manifest C:\Users\BLOWKA\Documents\Minimax\r2-manifest.json
```

Без ключей объекты тоже можно грузить через CLI (одна команда на файл, без подписи):

```
cf r2 objects put site/<ключ> --bucket-name gremovod --file <путь> --content-type <тип>
```

## Код в студии

`backend/r2_storage.py` — S3-клиент с подписью SigV4 (регион `auto`, сервис `s3`), сверенной
побайтово с botocore. Функции: `put_bytes`, `put_file`, `get_bytes`, `public_get`, `head`, `delete`.
Публичное чтение без ключей — `public_get`, оно не подписывает запрос.
`backend/test_r2_storage.py` — 16 проверок без сети.
