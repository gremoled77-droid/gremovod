# Грэм: пакет из 8 ракурсов на GPT Image 2.5 (промпты, 24.10.2026)

Источники правил: `docs/master-prompts/photo-gpt-image-2.5.md` (книга и гайд OpenAI), профиль героя `projects/GremoVOD/01_Персонажи/Грэм/ПРОФИЛЬ.json`. Платных вызовов здесь нет: промпты запускает владелец в Codex.

## Как запускать
1. Приложить **Image 1 = утверждённый портрет** (лицо) и **Image 2 = полный рост** (рабочий образ от 15.10.2026), если есть. Если у владельца другие референсы Грэма, приложить их в том же порядке: сначала лицо, потом рост.
2. На каждый ракурс отправлять **общий блок + строку ракурса** (один ракурс за запрос). Каждый раз прикладывать **исходные** Image 1 и Image 2, а не предыдущий результат: так лицо не уплывает.
3. Размер: для лица 1024x1024 (или 1536x1024), для роста 1024x1536 вертикально; quality high. Размер и качество задаются параметрами запуска, не текстом.
4. Утверждать вручную по списку проверки внизу. Новые версии автоматически не утверждаются.
5. Имена файлов для импорта в студию: `grem_face_front.png`, `grem_face_34_left.png`, `grem_face_34_right.png`, `grem_face_profile.png`, `grem_body_front.png`, `grem_body_back.png`, `grem_body_left.png`, `grem_body_right.png` («left/right» = слева/справа **от зрителя**: кто стоит лицом или боком в эту сторону).

## Общий блок (вставлять перед строкой ракурса)
```
Scene: Plain seamless light-gray studio background, soft even light, no props, no text, no watermark. Character reference sheet style.
Subject: Use Image 1 as the character reference for Grem: keep his face, age, body build and the exact art style (same level of stylization, shading and colors). Use Image 2 for his full-body proportions and outfit. Grem is a fictional Minsk taxi driver: wide lower face, full cheeks, pronounced nasolabial folds, asymmetric eyebrows, brown eyes with a sly squint, closed half-smile, short dark beard with gray, wide mustache. Outfit: red corduroy flat cap, plain black T-shirt, dark straight trousers, dark shoes. Stocky, not slim or athletic.
Constraints: Do not change the face, age, build or cap. Same facial features, proportions and color palette as Image 1. No accessories, no logos, no cat features, no extra people, no extra text. Do not add new elements.
```

## Строки ракурсов (по одной после общего блока)
1. **Лицо анфас** (`grem_face_front`)
```
Camera and light: Head-and-shoulders portrait, camera at eye level, looking straight into the camera, neutral head position, signature sly squint and closed half-smile. Soft even front light.
```
2. **Лицо 3/4 слева** (`grem_face_34_left`)
```
Camera and light: Head-and-shoulders portrait, three-quarter view, his face turned toward the viewer's left by about 45 degrees, eye level, same sly squint and closed half-smile. Soft even front light.
```
3. **Лицо 3/4 справа** (`grem_face_34_right`)
```
Camera and light: Head-and-shoulders portrait, three-quarter view, his face turned toward the viewer's right by about 45 degrees, eye level, same sly squint and closed half-smile. Soft even front light.
```
4. **Профиль** (`grem_face_profile`)
```
Camera and light: Head-and-shoulders portrait, pure side profile facing the viewer's left, eye level, cap, beard and mustache clearly readable in silhouette. Soft even light.
```
5. **Рост спереди** (`grem_body_front`)
```
Camera and light: Full body visible, feet included, standing relaxed with arms at his sides, facing the camera straight on, camera at chest height, normal perspective. Soft even light.
```
6. **Рост сзади** (`grem_body_back`)
```
Camera and light: Full body visible, feet included, seen from directly behind, standing relaxed with arms at his sides, camera at chest height. Show the back of the cap and the black T-shirt. Soft even light.
```
7. **Рост слева** (`grem_body_left`)
```
Camera and light: Full body visible, feet included, side view, his body facing the viewer's left, standing relaxed with arms at his sides, camera at chest height. Soft even light.
```
8. **Рост справа** (`grem_body_right`)
```
Camera and light: Full body visible, feet included, side view, his body facing the viewer's right, standing relaxed with arms at his sides, camera at chest height. Soft even light.
```

## Точечная правка (если ракурс почти хорош)
```
Use Image 1 as the picture to edit.
Change only: <what exactly, one thing>.
Keep everything else unchanged: face, age, build, outfit, pose, background and lighting. Do not add new elements or text.
```

## Список проверки перед утверждением
- Лицо тот же человек (усы, борода с сединой, складки, асимметричные брови, прищур).
- Кепка красная вельветовая плоская, футболка чёрная, брюки и ботинки тёмные; без логотипов и аксессуаров.
- Комплекция коренастая, не стройная; рост и пропорции между ракурсами совпадают.
- Фон ровный светло-серый, без теней на фоне и текста.
- «Слева/справа» соответствует названию файла (от зрителя).

## Что не проверено
Книга и гайд не описывают поворот персонажа по ракурсам и не дают лимит референсов; точность «45 градусов» и профиля проверить на первых двух картинках и при необходимости заменить словами «turned to show his left cheek».
