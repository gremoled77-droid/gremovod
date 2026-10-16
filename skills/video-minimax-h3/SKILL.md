---
name: "video-minimax-h3"
description: "Use when writing a prompt for MiniMax H3 (Hailuo 3.0) video: Omni Reference with Image 1/Video 1/Audio 1 role assignment, First/Last Frame, timing, native audio; for the GremoVOD cartoon."
---

# MiniMax H3 (Hailuo 3.0) — промпты для видео

Статус: модель уже в каталоге (`minimax-h3`, проверена вживую с одним референсом-картинкой). **Omni Reference (много референсов) через студию не проверен**: адаптер сейчас отдаёт 1 картинку. Правила ниже из инструкции владельца.

## Режимы (взаимоисключающие)

- Text-to-Video — без референсов, подробнее описать сцену.
- First/Last Frame — указать, какое изображение открывает, какое закрывает.
- Omni Reference (Ref-to-Video) — до 9 изображений + 3 видео (до 15 с суммарно) + 3 аудио (до 15 с), всего до 12 файлов. Аудио не может быть единственным референсом. **С First/Last Frame не комбинируется.**

## Референсы: назначать роль, не описывать содержимое

Теги: `Image 1`, `Image 2`, `Video 1`, `Audio 1` (без `@`, словами с пробелом).

- Плохо: `Image 1 — a man with brown hair in a blue jacket in a park`.
- Хорошо: `Image 1 defines Грэм — lock identity and wardrobe throughout`.
- После назначения имени дальше обращаться по имени (`Грэм`), без `Image 1`.
- Роль на референс одна: identity, product, style, motion, camera, voice, rhythm.
- Лучше 2 чётких референса, чем 9 расплывчатых.
- Лицо: фронтальный портрет на нейтральном фоне. Силуэт и причёска: второй референс в полный рост. Мелкая деталь (значок, шашечки): третий референс с крупным планом. Готовый набор ракурсов: коллаж/лист героя из `../video-seedance-2-0/references/character-sheet-and-storyboard.md`.

## Порядок промпта (Omni)

1. Роли всех референсов.
2. Формат: `16:9`, `9:16`, `1:1`, `4:3`, `3:4`, `21:9` или `adaptive`.
3. Одно предложение: субъект, сцена, событие, стиль, подход камеры.
4. Раскладка действия по времени.
5. Что зафиксировать (identity, геометрия машины, одежда, текст на объектах).
6. Только критичные запреты.

Длительность одной генерации 4–15 с (в документации до 20). Простой ролик — одно связное описание без дробления; сложный — открывающее состояние → изменения → финальное состояние. Движение камеры и объекта разделять: `Грэм turns head right while camera pans left`. Приёмы камеры: dolly in, orbital, crane, tracking, handheld, locked-off, macro, crash zoom, low angle.

## Шаблон

```
Image 1 defines Грэм — lock identity and wardrobe. Image 2 defines the ВАЗ-2106 — lock shape, color, plates. Audio 1 — voice reference.
Format 9:16.
Грэм drives through rainy Minsk at dusk and stops to pick up a late passenger; handheld tracking, 2K, 24fps, film grain, warm amber against cold teal.
0-4s: car rolls into frame, camera tracks alongside. 4-9s: Грэм looks at the passenger in the mirror, lip sync to Audio 1. 9-12s: car pulls away, locked-off wide.
Preserve identity and wardrobe throughout. No morphing. No deformation. No flickering. Stable face and car geometry. Realistic physics. 2K cinematic, native audio.
```

## Звук

Нативный (диалоги, эффекты, окружение), отдельно включать не надо. Голос по образцу: `voice reference Audio 1 exactly`, `lip sync reference Audio 1`. Ритм: `match pacing to Audio 1's beat`. Звук из видео-референса: `reference Video 1's audio track`. Мультиязычный диалог поддерживается; язык русский проверить тестом.

## Чего избегать

- Размытые «cool/nice/beautiful».
- Противоречивые роли референсов, много несвязанных сцен в одной генерации.
- Длинный список запретов: оставить только то, что реально ломает результат (identity morphing, лишние пальцы, мерцание света, скачки камеры).
- Знаменитости и защищённые персонажи.
- Лимит символов промпта зависит от обёртки (у RunDiffusion 7000): проверять у PiAPI.

## Технический хвост

`Preserve identity and wardrobe throughout. No morphing. No deformation. No flickering. Stable face and product geometry across the clip. Realistic physics. 2K cinematic, native audio.`
