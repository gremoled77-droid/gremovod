# Моушн и монтаж кодом: что установлено (2026-10-18)

Всё стоит **вне репозитория студии**: скиллы — в `~/.claude/skills` (видны Claude Code в любой папке), исходники и окружения — в `~/motion-tools`. Ключи API нигде не прописаны.

Промпт «студии моушна» (планка, правила движения, петля проверки по кадрам): `docs/MOTION_STUDIO_PROMPT.md`.

## Движки

| Что | Где | Лицензия | Проверка |
|---|---|---|---|
| HyperFrames (HTML + GSAP → MP4, Chrome + ffmpeg) | `npx hyperframes@0.8.169 …` | Apache-2.0 | Пробный рендер `~/motion-tools/smoke/smoke-test`: 10 с, 1920×1080, 1 мин 07 с, MP4 открывается |
| Remotion (React → MP4) | ставится в проект через `npx create-video@latest`; есть в `OpenMontage/remotion-composer` | Remotion License: бесплатно для частного лица и фирм до 3 сотрудников | Рендер не запускался |

Телеметрия HyperFrames выключена (`hyperframes telemetry disable`). Скиллы ставились с `DISABLE_TELEMETRY=1`.

## Скиллы (`~/.claude/skills`)

- **HyperFrames**: `hyperframes` (вход), `hyperframes-core/-animation/-creative/-keyframes/-audio/-cli/-registry/-studio`, `media-use`, `motion-graphics`, `general-video`, `music-to-video`, `faceless-explainer`, `embedded-captions`, `talking-head-recut`.
- **Remotion**: `remotion-best-practices` (вход), `-create`, `-markup`, `-render`, `-studio`, `-captions`, `-docs`.
- **GSAP**: `gsap-core`, `-timeline`, `-plugins`, `-utils`, `-react`, `-frameworks`, `-performance`, `-scrolltrigger`.
- **product-launch-motion** (Chan): springs, seek(t), Playwright-подкадры, ffmpeg tmix, бит-сетка.
- **motion-design** (Howseen): тот же подход + «Remake mode». Исходник `~/motion-tools/claude-motion-design`. Python-пакеты `playwright imageio-ffmpeg numpy pillow` + Chromium поставлены в пользовательский Python 3.13.
- **video-use** (browser-use): монтаж записи по расшифровке. Ссылка-junction на `~/motion-tools/video-use`, окружение через `uv sync` (запуск хелперов: `uv run python helpers/<name>.py`).
- **editor**, **watch** (Diffusion Studio): нужен десктоп-клиент.

## Приложения

- **OpenMontage** — `~/motion-tools/OpenMontage` (AGPL-3.0). `.venv` с `requirements.txt` + `piper-tts`, `remotion-composer` с `npm install`. Работать: открыть Claude Code в этой папке (там свой CLAUDE.md и `.claude/skills`). Для мультсериала интересен пайплайн `character-animation` (SVG-риги, GSAP, HyperFrames).
- **Diffusion Studio** — десктоп-клиент **не установлен**: скачать Windows x64 вручную с diffusion.studio/download.

## Что сделать владельцу

1. Ключ ElevenLabs для video-use: вписать самому в `~/motion-tools/video-use/.env` (`ELEVENLABS_API_KEY=`). Звук каждого исходника уходит в ElevenLabs Scribe — это платно.
2. Ключи для OpenMontage (по желанию): `~/motion-tools/OpenMontage/.env`. Без ключей работает Piper TTS, Remotion, HyperFrames, ffmpeg. С ключами промпты и картинки уходят выбранным провайдерам.
3. Diffusion Studio — установить клиент вручную, если нужен.

## Осторожно

- Скиллы работают с полными правами агента; перед первым запуском стоит просмотреть SKILL.md.
- `motion-design/scripts/mixkit_sfx_search.py` и `svgl_logos.py` ходят в интернет с подменённым User-Agent — по правилам студии их не запускать без вопроса.
- `media-use` и облачный рендер HyperFrames могут отправлять материалы в HeyGen; рендерить локально.
- Remake mode (motion-design) повторяет чужой ролик кадр в кадр — только для учёбы, не для выпуска.

## Обновление

```bash
npx skills update -g
```
