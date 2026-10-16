"""Встроенные рецепты рилсов.

Идеи и приёмы взяты из разбора паков промптов BALTÈON (сентябрь и октябрь 2026), см.
docs/PROMPT_PACK_ANALYSIS_2026-10-16.md. Тексты промптов написаны для студии заново, это не копии.
В шаблонах {{поле}} подставляется значением из формы, {{look}} — выбранным стилем изображения.
Рецепт не считается проверенным, пока `verified_at` пуст: ни один из них вживую не запускался.
"""

SOURCE = 'Идея: пак BALTÈON, '

# Стиль изображения. Общий для всех рецептов; рецепт перечисляет, какие стили ему подходят.
LOOKS = {
    'phone': {
        'label': 'Реализм: съёмка на телефон',
        'text': 'Raw vertical smartphone footage, handheld with small natural shake, autofocus that hunts a little, '
                'phone sensor noise, natural light, no colour grading, no slow motion. Photoreal live action, not CGI, '
                'not glossy, real skin texture.',
    },
    'dashcam': {
        'label': 'Реализм: видеорегистратор',
        'text': 'Wide-angle dashcam footage from behind the windshield, slight fisheye, flat overcast colours, '
                'compression softness, no colour grading, no slow motion. Photoreal live action, not CGI.',
    },
    'cctv': {
        'label': 'Реализм: камера наблюдения',
        'text': 'Security-camera footage from a high corner, slight fisheye, washed greenish-grey colours, soft video '
                'noise. The camera is a PTZ unit that pans and zooms slowly to follow the action, never jumps. '
                'Photoreal live action, not CGI. No timestamp, no on-screen text.',
    },
    'film': {
        'label': 'Кино: 35 мм',
        'text': 'Cinematic 35mm anamorphic film look, fine grain, soft halation, warm backlight, deep shadows, '
                'natural skin with pores, not glossy, not plastic.',
    },
    'vhs': {
        'label': 'Реализм: кассета VHS',
        'text': 'Home-video camcorder tape: interlaced softness, colour bleed, tape noise, small tracking wobble at the '
                'bottom, blown highlights on bright lights, auto-zoom that pumps. Vertical crop of a 4:3 picture. '
                'No on-screen date or text.',
    },
    'cartoon': {
        'label': 'Мультфильм: стиль сериала',
        'text': 'Stylised 3D-animated cartoon look matching the supplied character and location references: clean '
                'shapes, soft cartoon shading, expressive faces, consistent proportions in every frame. Not photoreal. '
                'Keep the same visual style as the references.',
    },
}

HERO = 'the taxi driver Graham from @Image1'

RECIPES = [
    {
        'id': 'night-visitor',
        'title': 'Ночной гость у машины',
        'emoji': '🌲',
        'family': 'Страшилка',
        'kind': 'one_take',
        'difficulty': 'средне',
        'hook': 'Ночь, остановились на лесной дороге. Один зверь спереди на капоте, а второй, невидимый до последней секунды, бьёт в боковое стекло.',
        'duration': 10,
        'aspect_ratio': '9:16',
        'resolution': '720p',
        'audio': True,
        'looks': ['phone', 'cartoon'],
        'ref_slots': [
            {'n': 1, 'role': 'Лицо и одежда героя', 'required': True, 'note': 'Один человек: ни фона, ни второго лица.'},
            {'n': 2, 'role': 'Салон машины', 'required': True, 'note': 'Торпедо, руль, сиденья: геометрия кабины.'},
            {'n': 3, 'role': 'Боковое окно', 'required': False, 'note': 'Окно пассажира и зеркало, нужны для финала.'},
            {'n': 4, 'role': 'Зверь', 'required': True, 'note': 'Только зверь. Лучше реальное фото или чёткий кадр.'},
            {'n': 5, 'role': 'Ночная дорога в свете фар', 'required': False, 'note': 'Свет и зерно, не люди.'},
        ],
        'fields': [
            {'key': 'hero', 'label': 'Герой', 'default': HERO, 'hint': 'Кто за рулём'},
            {'key': 'creature', 'label': 'Зверь', 'default': 'brown bear', 'hint': 'Одно слово: медведь, волк, лось'},
            {'key': 'place', 'label': 'Место', 'default': 'a narrow forest road near Minsk at night'},
            {'key': 'line', 'label': 'Реплика героя шёпотом', 'default': 'Ты это видишь?', 'hint': 'Одна короткая фраза'},
        ],
        'beats': [
            {'t': '0–3 с', 'text': 'Зверь спереди идёт на свет фар, герой шепчет реплику.'},
            {'t': '3–7 с', 'text': 'Зверь кладёт лапы на капот. Герой блокирует двери. Второй зверь не виден.'},
            {'t': '7–10 с', 'text': 'Удар в боковое стекло, камера дёргается после удара, второй зверь у самого стекла. Обрыв.'},
        ],
        'why': [
            'Каждому референсу одна роль: лицо не отвечает за локацию, салон не отвечает за зверя.',
            'Причина и следствие в одном дубле: сначала удар, потом реакция камеры.',
            'Свет фар и салона зафиксирован на всё видео, иначе модель «перекрашивает» сцену.',
            'Второй зверь невидим до финала, поэтому последние секунды дают резкую отдачу.',
        ],
        'pitfalls': [
            'Не пиши «страшное кино»: сначала реальные сущности (герой, салон, зверь), потом эмоция.',
            'Если в рефах есть зверь из прошлого ролика, он вылезет вместо нового.',
            'Звери только снаружи машины, это пишется явно.',
        ],
        'source': SOURCE + 'сентябрь 2026, ролик «Медведь»',
        'steps': [
            {
                'title': 'Видео', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 10,
                'prompt': '''REFERENCES: @Image1 is the driver: keep his face and clothes exactly, never duplicate him. @Image2 is the car interior geometry. @Image3 is the passenger window and mirror. @Image4 is the {{creature}}: realistic anatomy and scale. @Image5 is the night road and headlight look. There are exactly two {{creature}}s in the story.
LOOK: {{look}}
WORLD LOCK: one car, one driver, one uninterrupted take from inside the car, engine idling. Headlights, dashboard glow and surroundings never change. No cuts, no time jumps, no extra animals.
0-3s: {{hero}} sits in the stopped car on {{place}}. The camera looks past him through the windshield. The first {{creature}} walks slowly toward the car along the road in the headlights. The driver whispers in Russian: "{{line}}" The passenger window must show nothing yet.
3-7s: same take. The first {{creature}} reaches the car and rests both front paws on the hood, its face close to the glass. The driver locks the doors and stays still. The second {{creature}} is still completely invisible: no shadow, no reflection.
7-10s: something heavy hits the passenger window FIRST, and only after the impact the camera jerks toward it. The second {{creature}} stands right outside the glass, its face almost touching it. Mirror and door frame stay visible so it is clear the animal is outside. End on its face. No explanation, no title card.
AUDIO: engine idle, tense breathing, one heavy knock on glass. No music, no other speech.
RULES: exactly one driver and two animals. Nothing enters the car, nothing breaks, no gore, no cut.''',
            },
        ],
    },
    {
        'id': 'dashcam-incident',
        'title': 'Запись регистратора',
        'emoji': '🚕',
        'family': 'Такси',
        'kind': 'one_take',
        'difficulty': 'просто',
        'hook': 'Обычный вечерний рейс по Минску. В кадр выходит нелепая деталь, водитель сухо комментирует, ролик обрывается на реакции.',
        'duration': 10,
        'aspect_ratio': '9:16',
        'resolution': '720p',
        'audio': True,
        'looks': ['dashcam', 'cartoon'],
        'ref_slots': [
            {'n': 1, 'role': 'Капот и торпедо такси', 'required': False, 'note': 'Вид изнутри, чтобы машина совпадала.'},
            {'n': 2, 'role': 'Странный объект', 'required': False, 'note': 'Только он, обрезанный до нужного.'},
            {'n': 3, 'role': 'Голос героя (лицо)', 'required': False, 'note': 'Нужен, только если лицо водителя попадает в кадр.'},
        ],
        'fields': [
            {'key': 'place', 'label': 'Улица', 'default': 'a wet evening avenue in Minsk with mixed traffic'},
            {'key': 'event', 'label': 'Что выходит в кадр', 'default': 'a huge goose in a high-visibility vest walks onto the crossing like a pedestrian'},
            {'key': 'line', 'label': 'Реплика водителя', 'default': 'Ну всё, приехали.'},
        ],
        'beats': [
            {'t': '0–3 с', 'text': 'Обычный поток машин, водитель ворчит себе под нос.'},
            {'t': '3–7 с', 'text': 'В кадр выходит нелепая деталь, регистратор дёргается от торможения.'},
            {'t': '7–10 с', 'text': 'Все замерли, реплика, обрыв на детали.'},
        ],
        'why': [
            'Самый дешёвый способ проверить связку «рецепт → Seedance → рилс»: один план, одна шутка.',
            'Регистратор в такси это естественная камера для нашего героя.',
            'Все машины в кадре разные, иначе модель нарисует ряд одинаковых.',
        ],
        'pitfalls': [
            'Не описывай ряд одинаковых машин: пиши «разные марки и цвета, никогда одинаковые».',
            'Реф тянет всё, что на нём есть: объект рефом обрежь до нужного.',
            'Вывески рисуются псевдо-кириллицей: пиши, что все надписи пустые или размыты.',
        ],
        'source': SOURCE + 'сентябрь 2026, «Эффект бабочки 2» (кадр регистратора)',
        'steps': [
            {
                'title': 'Видео', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 10,
                'prompt': '''REFERENCES: @Image1 shows the taxi hood and dashboard to match. @Image2 shows the unusual object to copy exactly and nothing else from its frame. If @Image3 is supplied it is the face of the driver, used only for his face.
LOOK: {{look}}
WORLD LOCK: one continuous shot from the taxi windshield along {{place}}. Traffic is made of different makes and colours, never identical cars. All signs are blank or blurred, no readable text anywhere.
0-3s: ordinary evening traffic, the taxi moves slowly. The driver mutters in Russian under his breath, unseen or barely seen.
3-7s: {{event}}. The taxi brakes, the image lurches, other cars react naturally.
7-10s: everything stops. The driver says one line in Russian: "{{line}}" Hold on the strange detail in the middle of the road and end.
AUDIO: engine, horns far away, tyres on wet asphalt, one spoken line. No music.
RULES: nobody is hurt, no blood, no cuts, no title, no logos.''',
            },
        ],
    },
    {
        'id': 'creature-passenger',
        'title': 'Пассажир-тварь',
        'emoji': '☕',
        'family': 'Твари',
        'kind': 'two_step',
        'difficulty': 'средне',
        'hook': 'В такси садится существо со спокойным человеческим лицом и телом из еды или предмета. Одна фраза, шутка, финал взглядом в камеру.',
        'duration': 15,
        'aspect_ratio': '9:16',
        'resolution': '720p',
        'audio': True,
        'looks': ['phone', 'cartoon'],
        'ref_slots': [
            {'n': 1, 'role': 'Тварь (картинка из шага 1)', 'required': True, 'note': 'Сначала генерируем кадр, потом видео по нему.'},
            {'n': 2, 'role': 'Салон такси (место съёмки)', 'required': False, 'note': 'Задний ряд или вид с торпедо.'},
        ],
        'fields': [
            {'key': 'hero', 'label': 'Водитель', 'default': 'the taxi driver Graham, an ordinary human'},
            {'key': 'passenger', 'label': 'Лицо пассажира', 'default': 'a kind elderly woman in a floral headscarf'},
            {'key': 'material', 'label': 'Из чего тело', 'default': 'dark brewed tea with soggy teabags and lemon slices'},
            {'key': 'line1', 'label': 'Первая реплика', 'default': 'До вокзала, пожалуйста.'},
            {'key': 'line2', 'label': 'Вторая реплика', 'default': 'Только без музыки, сынок.'},
        ],
        'beats': [
            {'t': '0–3 с', 'text': 'Тварь садится на заднее сиденье, говорит первую реплику.'},
            {'t': '3–7 с', 'text': 'Водитель оборачивается, тварь вторую реплику говорит спокойно.'},
            {'t': '7–12 с', 'text': 'Нелепый эпизод: тело течёт, брызжет, водитель в шоке.'},
            {'t': '12–15 с', 'text': 'Тварь смотрит прямо в камеру. Заморозка.'},
        ],
        'why': [
            'Спокойное человеческое лицо на невозможном теле: на этом держится вся серия.',
            'Сначала картинка существа, потом видео по ней: лицо не плывёт между битами.',
            'Камера «найденной записи» всё время движется, неподвижная камера выглядит мёртвой.',
        ],
        'pitfalls': [
            'Модерация режет слова, а не еду: не пиши «съест», «укусит», «горячий чай на голову». Пиши «silly harmless mascot».',
            'Возраст цифрами и «усы» в промпте не пиши: «kind calm face of an elderly woman».',
            'Три реплики на 15 с максимум. Речь проверяй на слух; кривое слово чинится озвучкой поверх.',
            'Референсы JPEG до 500 КБ: тяжёлый PNG рвёт загрузку.',
        ],
        'source': SOURCE + 'октябрь 2026, серия «Твари», ролики 1–3',
        'steps': [
            {
                'title': 'Шаг 1. Картинка существа', 'kind': 'image', 'model': 'gpt-image-2', 'aspect_ratio': '9:16',
                'prompt': '''{{look}}
A tall thin hunched creature about 2.3 metres tall sits in the back seat of an old taxi. Its head is a completely normal, calm, kind head of {{passenger}}, natural skin, gentle smile straight into the camera. Below the neck the body is not human: it is made of {{material}}, with absurdly long spindly arms and legs. Silly, harmless, like a mascot. No text, no logos.''',
            },
            {
                'title': 'Шаг 2. Видео', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 15,
                'prompt': '''REFERENCES: @Image1 is the creature and must look exactly like the picture in every frame, the face never changes. @Image2 is the taxi interior.
LOOK: {{look}} One continuous take, filmed by the driver's phone mounted on the dashboard. The phone shakes on bumps and never sits perfectly still. No on-screen text.
Characters: the driver ({{hero}}), ordinary and human. Only one creature, no other creatures.
0-3s: the creature gets into the back seat of the taxi and says in Russian: "{{line1}}"
3-7s: the driver turns his head. The creature calmly says in Russian: "{{line2}}" and looks around the cabin.
7-12s: a funny physical gag with the creature's body ({{material}} wobbles, drips or squeezes in the seat), the driver stares, nobody is hurt.
12-15s: the creature turns its calm face straight into the camera. Freeze on the face for the last half second.
AUDIO: engine, road bumps, soft squelching, the two Russian lines. No music.
NEGATIVE: no second creature, no changed face, no cartoon face in realistic looks, no melting face, no human legs on the creature, no text, no logos, no blood, no biting, nobody gets eaten, nobody gets hurt.''',
            },
        ],
    },
    {
        'id': 'creature-chase',
        'title': 'Две твари: погоня',
        'emoji': '🏃',
        'family': 'Твари',
        'kind': 'two_step',
        'difficulty': 'сложно',
        'hook': 'Двор или магазин, две твари с разными лицами. Одна бросает фразу, вторая бежит, ломая всё вокруг, финал: обе смотрят в камеру.',
        'duration': 15,
        'aspect_ratio': '9:16',
        'resolution': '720p',
        'audio': True,
        'looks': ['phone', 'cartoon'],
        'ref_slots': [
            {'n': 1, 'role': 'Тварь A (картинка)', 'required': True, 'note': 'Отдельный кадр для каждой.'},
            {'n': 2, 'role': 'Тварь B (картинка)', 'required': True, 'note': 'Лицо и материал тела отличаются от A.'},
            {'n': 3, 'role': 'Место действия', 'required': False, 'note': 'Одна картинка локации без людей.'},
        ],
        'fields': [
            {'key': 'creatureA', 'label': 'Тварь A', 'default': 'a thin creature with a calm face of an elderly woman and a body of brewed tea'},
            {'key': 'creatureB', 'label': 'Тварь B', 'default': 'a thin creature with a calm face of a middle-aged man and a body of glossy condensed milk'},
            {'key': 'place', 'label': 'Место', 'default': 'a bright Minsk supermarket aisle'},
            {'key': 'line', 'label': 'Крик погони', 'default': 'Сгущёночки к чаю!'},
        ],
        'beats': [
            {'t': '0–3 с', 'text': 'Тварь B стоит спокойно, A входит в кадр и тихо говорит фразу.'},
            {'t': '3–7 с', 'text': 'B срывается и бежит, A за ней, всё летит с полок.'},
            {'t': '7–12 с', 'text': 'Погоня идёт через магазин, A кричит реплику.'},
            {'t': '12–15 с', 'text': 'A загоняет B в угол, обе смотрят в камеру. Заморозка.'},
        ],
        'why': [
            'Две твари: Seedance держит обе, если у каждой свой референс и в промпте «must look exactly like its reference».',
            'Сюжет простой: встреча, погоня, обе в камеру. Три твари плюс погоня уже лотерея.',
            'Финал «все смотрят в камеру» это обрыв, который рождает комментарии «а дальше?».',
        ],
        'pitfalls': [
            'Если одна тварь пропала в середине, сначала проверь сетку кадров: часто хватает монтажа.',
            'Не клади четвёртую тварь: модель путает, кто есть кто.',
            'Опасное направляй в предметы, не в лица: «no fighting, no biting, nobody gets hurt».',
        ],
        'source': SOURCE + 'октябрь 2026, серия «Твари», ролики 2–4',
        'steps': [
            {
                'title': 'Шаг 1А. Картинка твари A', 'kind': 'image', 'model': 'gpt-image-2', 'aspect_ratio': '9:16',
                'prompt': '''{{look}}
Inside {{place}}: {{creatureA}}, about 2.3 metres tall, spindly arms and legs, a completely normal calm kind face looking into the camera. Silly, harmless, like a mascot. No text, no logos.''',
            },
            {
                'title': 'Шаг 1Б. Картинка твари B', 'kind': 'image', 'model': 'gpt-image-2', 'aspect_ratio': '9:16',
                'prompt': '''{{look}}
Inside {{place}}: {{creatureB}}, about 2.3 metres tall, spindly arms and legs, a completely normal calm face looking into the camera. Silly, harmless, like a mascot. No text, no logos.''',
            },
            {
                'title': 'Шаг 2. Видео', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 15,
                'prompt': '''REFERENCES: @Image1 is CREATURE A, @Image2 is CREATURE B, @Image3 is the location. Each creature must look exactly like its reference image in every frame; faces never change.
LOOK: {{look}} One continuous take filmed by a frightened bystander who runs after them, the camera shaking and never still.
Only these two creatures, no others and no other speaking characters.
0-3s: B stands calmly in the middle of {{place}}. A skitters into the frame and quietly says a Russian line to it.
3-7s: B sprints away on long legs, A chases it at full speed; objects fall off the shelves behind them with loud clatter.
7-12s: the chase tears across the location. A screams in Russian: "{{line}}"
12-15s: A corners B. Both slowly turn their calm faces to the camera. Freeze on the two faces for the last half second.
AUDIO: location ambience, clatter, wet squelching steps, the Russian lines. No music.
NEGATIVE: no third creature, no changed faces, no melting faces, no human legs, no text, no logos, no blood, no injury, no fighting, nobody gets eaten.''',
            },
        ],
    },
    {
        'id': 'cctv-queue',
        'title': 'Камера наблюдения: очередь',
        'emoji': '📹',
        'family': 'Твари',
        'kind': 'two_step',
        'difficulty': 'средне',
        'hook': 'Видео с потолка коридора: двое сидят в очереди, третий проходит без очереди со словами «я только спросить». Через секунду из кабинета вылетает человек.',
        'duration': 15,
        'aspect_ratio': '9:16',
        'resolution': '720p',
        'audio': True,
        'looks': ['cctv'],
        'ref_slots': [
            {'n': 1, 'role': 'Персонаж 1 в очереди', 'required': True, 'note': 'Картинка из шага 1.'},
            {'n': 2, 'role': 'Персонаж 2 в очереди', 'required': True, 'note': ''},
            {'n': 3, 'role': 'Тот, кто идёт без очереди', 'required': True, 'note': ''},
        ],
        'fields': [
            {'key': 'place', 'label': 'Коридор', 'default': 'a state polyclinic corridor with pale green walls and plastic chairs'},
            {'key': 'c1', 'label': 'Персонаж 1', 'default': 'a tall thin creature with a calm man face and a body of glossy condensed milk'},
            {'key': 'c2', 'label': 'Персонаж 2', 'default': 'a tall thin creature with a calm young woman face and a body of pink plush fur'},
            {'key': 'c3', 'label': 'Персонаж 3', 'default': 'a tall thin creature with a calm elderly woman face and a body of brewed tea'},
            {'key': 'line1', 'label': 'Вопрос', 'default': 'Вы последний?'},
            {'key': 'line2', 'label': 'Фраза без очереди', 'default': 'Я только спросить.'},
        ],
        'beats': [
            {'t': '0–3 с', 'text': 'Широкий высокий ракурс, двое сидят с талончиками, третий подходит и спрашивает.'},
            {'t': '3–7 с', 'text': 'Камера доворачивается к двери, третий идёт мимо очереди.'},
            {'t': '7–12 с', 'text': 'Из-за двери шум, дверь распахивается, оттуда бежит человек в халате.'},
            {'t': '12–15 с', 'text': 'Коридор пуст, третий выходит с чашкой и смотрит в объектив. Заморозка.'},
        ],
        'why': [
            'Камера наблюдения сразу читается как «настоящая запись».',
            'PTZ-камера сама доворачивается за действием: прибитый кадр был бы скучным, дрожащий телефон тут не к месту.',
            'Реплики из жизни: «Вы последний?», «Я только спросить».',
        ],
        'pitfalls': [
            'Таймкод Seedance рисует как попало: закрой его размытием и поставь свой в монтаже.',
            'Людей в очереди нет специально: четвёртое существо или толпа, и лица теряются.',
            'Кривую реплику чини озвучкой поверх, не новым дублем; голосовой образец не короче 5 секунд.',
        ],
        'source': SOURCE + 'октябрь 2026, ролик «Я только спросить»',
        'steps': [
            {
                'title': 'Шаг 1А. Картинка персонажа 1', 'kind': 'image', 'model': 'gpt-image-2', 'aspect_ratio': '9:16',
                'prompt': '''{{look}}
Standing in {{place}}: {{c1}}, a completely normal calm face looking at the camera, silly harmless mascot, no text, no logos.''',
            },
            {
                'title': 'Шаг 1Б. Картинка персонажа 2', 'kind': 'image', 'model': 'gpt-image-2', 'aspect_ratio': '9:16',
                'prompt': '''{{look}}
Standing in {{place}}: {{c2}}, a completely normal calm face looking at the camera, silly harmless mascot, no text, no logos.''',
            },
            {
                'title': 'Шаг 1В. Картинка персонажа 3', 'kind': 'image', 'model': 'gpt-image-2', 'aspect_ratio': '9:16',
                'prompt': '''{{look}}
Standing in {{place}}: {{c3}}, a completely normal calm face looking at the camera, silly harmless mascot, no text, no logos.''',
            },
            {
                'title': 'Шаг 2. Видео', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 15,
                'prompt': '''REFERENCES: @Image1, @Image2 and @Image3 are three creatures; each must look exactly like its reference image in every frame, faces never change.
LOOK: {{look}} One continuous shot, high angle from the corner of {{place}}. No other text on screen.
Besides the three creatures there is one ordinary human doctor who appears later. No other creatures and no human queue.
0-3s: wide high angle down the corridor. Creature 1 and Creature 2 sit on the chairs, bored, holding paper queue tickets. Creature 3 walks up and asks in Russian: "{{line1}}" Creature 1 nods.
3-7s: the camera pans and zooms to the office door. Creature 3 walks past the queue, hand on the handle, and says in Russian: "{{line2}}" The other two turn their heads in sync.
7-12s: behind the door something loud happens, steam puffs from under it. The door flies open and the doctor runs out in panic down the corridor under the camera. Creature 1 jumps up and runs after him.
12-15s: the corridor is empty. Creature 3 steps out calmly with a teacup and looks straight up into the camera. The camera zooms to her face. Hold on her face.
AUDIO: fluorescent buzz, distant announcements, chairs creaking, running footsteps, the Russian lines. No music.
NEGATIVE: no extra creatures, no human patients, no changed faces, no text, no logos, no blood, no fighting, nobody gets hurt.''',
            },
        ],
    },
    {
        'id': 'frozen-time',
        'title': 'Время замерло',
        'emoji': '🧊',
        'family': 'Трюк',
        'kind': 'one_take',
        'difficulty': 'сложно',
        'hook': 'Герой спотыкается, всё взлетает и застывает. Камера плывёт сквозь замершие предметы и находит предмет-сюрприз, затем время включается снова.',
        'duration': 30,
        'aspect_ratio': '9:16',
        'resolution': '720p',
        'audio': False,
        'looks': ['film', 'cartoon'],
        'ref_slots': [
            {'n': 1, 'role': 'Лицо героя анфас', 'required': True, 'note': ''},
            {'n': 2, 'role': 'Лицо героя в профиль', 'required': False, 'note': ''},
            {'n': 3, 'role': 'Предмет-сюрприз в финале', 'required': False, 'note': 'Например, афиша, письмо или телефон.'},
        ],
        'fields': [
            {'key': 'hero', 'label': 'Герой', 'default': HERO},
            {'key': 'place', 'label': 'Место', 'default': 'a sunlit Minsk street market with small kiosks'},
            {'key': 'carry', 'label': 'Что он несёт', 'default': 'a thin bag of oranges and an open bottle of lemonade'},
            {'key': 'prize', 'label': 'Предмет в финале', 'default': 'a sheet of paper with a bold headline'},
        ],
        'beats': [
            {'t': '0–5 с', 'text': 'Герой идёт и разговаривает по телефону, в руках пакет и бутылка.'},
            {'t': '5–7 с', 'text': 'Спотыкается: апельсины и струя лимонада взлетают. Время замирает.'},
            {'t': '7–17 с', 'text': 'Камера плывёт сквозь замершие капли, находит муху в воздухе.'},
            {'t': '17–26 с', 'text': 'Облёт предмета-сюрприза и наезд до читаемого кадра.'},
            {'t': '26–30 с', 'text': 'Время включается, предметы падают, герой ловит телефон и ухмыляется.'},
        ],
        'why': [
            'Ключевая фраза: вся сцена замирает, движется только камера.',
            'У каждого предмета свой источник: апельсины из пакета, лимонад из бутылки. Иначе всё разваливается.',
            'Заморозка снимается либо статичной камерой, либо отдельным клипом со стоп-кадра.',
        ],
        'pitfalls': [
            'Самый дорогой формат: 30 с на 720p это $10,50 за одну попытку. Сначала проверь идею на 480p.',
            'Модель не держит одновременно заморозку и облёт. Если не вышло, режь на два клипа.',
            'Читаемый текст на листе обычно не получается: делай крупный план картинкой и подклеивай в монтаже.',
        ],
        'source': SOURCE + 'сентябрь 2026, ролики «Nokia × 90-е» и «Сон № 90»',
        'steps': [
            {
                'title': 'Видео', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 30,
                'prompt': '''REFERENCES: @Image1 and @Image2 are the hero's face, keep identity exact. @Image3 is the final object, reproduce it exactly.
LOOK: {{look}} One continuous shot, no cuts.
LOCATION: {{place}}.
STORY: {{hero}} walks along the stalls talking on a phone, carrying {{carry}}. He trips, everything flies up, time freezes, and the camera travels through his frozen world until it finds the final object. Then time snaps back.
0-5s: side tracking shot, he walks and talks cheerfully.
5-7s: he trips on the curb, the contents of his hands burst into the air, his phone flies out, and THE ENTIRE SCENE FREEZES IN TIME. From now on only the camera moves. His face is frozen in comic shock.
7-17s: the camera drifts slowly forward through the frozen objects, each hanging in the air; it passes very close to his face and settles on a single housefly frozen between the drops.
17-26s: the camera curves around the phone hanging in the air, then pushes in on {{prize}} that hangs behind it until it fills the frame.
26-30s: time restarts all at once: everything falls and bounces, he catches the phone with one hand, looks into the camera and smirks.
AUDIO: market ambience, silence during the freeze, the crash at the end.
RULES: during the freeze every subject stays perfectly still and only the camera moves. One hero, no extra limbs, no face drift, no cuts.''',
            },
        ],
    },
    {
        'id': 'selfie-animal',
        'title': 'Селфи со зверем',
        'emoji': '🤳',
        'family': 'Тренд',
        'kind': 'one_take',
        'difficulty': 'просто',
        'hook': 'Герой снимает селфи на причале. К нему втискивается зверь, на щелчок затвора делает человеческую улыбку и тут же её «выключает».',
        'duration': 10,
        'aspect_ratio': '9:16',
        'resolution': '720p',
        'audio': True,
        'looks': ['phone', 'cartoon'],
        'ref_slots': [
            {'n': 1, 'role': 'Лицо героя анфас', 'required': True, 'note': ''},
            {'n': 2, 'role': 'Лицо героя в профиль', 'required': False, 'note': ''},
            {'n': 3, 'role': 'Одежда (только одежда)', 'required': False, 'note': ''},
        ],
        'fields': [
            {'key': 'hero', 'label': 'Герой', 'default': HERO},
            {'key': 'animal', 'label': 'Зверь', 'default': 'ringed seal'},
            {'key': 'place', 'label': 'Место', 'default': 'a small wooden pier on a calm northern lake'},
        ],
        'beats': [
            {'t': '0–4 с', 'text': 'Герой поднимает телефон, зверь высовывается рядом, щека к щеке.'},
            {'t': '4–6,5 с', 'text': 'На щелчок затвора зверь расплывается в человеческую улыбку с белыми зубами, две секунды.'},
            {'t': '6,5–10 с', 'text': 'Улыбка гаснет раньше, чем герой повернёт голову. Зверь уходит под воду.'},
        ],
        'why': [
            'Весь тренд держится на одной секунде улыбки, всё остальное скучная камера «как с телефона».',
            'Голова зверя размером с голову героя и щека к щеке: за плечом не смешно.',
            'Улыбка гаснет до того, как герой посмотрит: пропадает ощущение «ничего не было».',
        ],
        'pitfalls': [
            'Не пиши «зубастая улыбка»: модель откроет пасть, выйдет зевок. Нужны слова: челюсти сомкнуты, уголки рта к глазам, человеческие зубы, глаза в щёлочки.',
            'Свою улыбку описывай отдельным блоком, иначе будут кривые зубы.',
            'Зверя меняй одной строкой, механика та же.',
        ],
        'source': SOURCE + 'октябрь 2026, ролик «Селфи с нерпой»',
        'steps': [
            {
                'title': 'Видео', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 10,
                'prompt': '''REFERENCES: @Image1 and @Image2 are the person's face; @Image3 is for his clothes only, take nothing else from it.
LOOK: {{look}} Vertical selfie video, one continuous take, no cuts, no music, no text. The camera is static with natural hand wobble, no zoom, no orbit.
LOCATION: {{place}}. World lock: location and light stay identical.
THE PERSON: {{hero}}, standing at the left of the frame, chest-up, holding a smartphone at arm's length. His smile is natural and friendly, a complete even row of healthy teeth, the mouth never opens wide.
THE ANIMAL: a real {{animal}} with an ordinary calm face and a closed mouth.
Beat 1 (0-4s): the person lifts the phone and smiles at it. The {{animal}} rises beside him and leans its big head in cheek to cheek at the same height, looking into the phone.
Beat 2 (4-6.5s): exactly on the phone's shutter click the animal's face snaps into a huge cheesy "say cheese" smile and holds it for two seconds. Jaws stay SHUT, teeth clenched, the corners of the mouth stretch up toward the eyes in a wide ear-to-ear U shape, showing two rows of big flat white human-like teeth, cheeks bulging, eyes squeezed into happy crescents. It is NOT an open mouth, NOT a yawn: no tongue, no fangs. The person does not notice.
Beat 3 (6.5-10s): the smile switches off instantly, the face is an ordinary animal face again, and only AFTER that the person glances sideways. The animal blinks and sinks into the water. The person looks back to the camera, shakes his head and chuckles.
AUDIO: wind, water on the pier, one clear phone shutter click, a short chuckle. No music, no speech.''',
            },
        ],
    },
    {
        'id': 'butterfly-chain',
        'title': 'Эффект бабочки',
        'emoji': '🦋',
        'family': 'Цепочка',
        'kind': 'chain',
        'difficulty': 'сложно',
        'hook': 'Мелкая небрежность героя запускает цепь происшествий, и в финале всё возвращается на его голову. Три клипа по 8 секунд, каждый стартует с последнего кадра предыдущего.',
        'duration': 24,
        'aspect_ratio': '9:16',
        'resolution': '720p',
        'audio': True,
        'looks': ['phone', 'film', 'cartoon'],
        'ref_slots': [
            {'n': 1, 'role': 'Клип 1: лицо героя', 'required': True, 'note': 'Клипы 2 и 3: последний кадр предыдущего клипа (кнопка «Последний кадр» в Кадрах).'},
            {'n': 2, 'role': 'Клип 1: профиль героя', 'required': False, 'note': ''},
            {'n': 3, 'role': 'Клип 1: одежда', 'required': False, 'note': ''},
        ],
        'fields': [
            {'key': 'hero', 'label': 'Герой', 'default': HERO},
            {'key': 'place', 'label': 'Место', 'default': 'a courtyard of grey Minsk apartment blocks at sunset'},
            {'key': 'trigger', 'label': 'Небрежность героя', 'default': 'tosses an empty coffee cup out of the taxi window without looking'},
            {'key': 'link1', 'label': 'Звено 1', 'default': 'the cup lands on a cyclist, who wobbles into a parked delivery scooter'},
            {'key': 'link2', 'label': 'Звено 2', 'default': 'the scooter rolls down the slope into a stall of watermelons'},
            {'key': 'finale', 'label': 'Финал', 'default': 'a rolling watermelon hits the taxi parked below and the roof light falls on the hero\'s head'},
        ],
        'beats': [
            {'t': 'Клип 1, 8 с', 'text': 'Небрежность героя. Кадр обрывается за полсекунды до контакта.'},
            {'t': 'Клип 2, 8 с', 'text': 'Старт с последнего кадра клипа 1. Два звена цепи.'},
            {'t': 'Клип 3, 8 с', 'text': 'Старт с последнего кадра клипа 2. Финал возвращается к герою.'},
        ],
        'why': [
            'Каждые ~3 секунды новый объект: невозможно угадать следующий кадр, поэтому досматривают.',
            'Кадр входа клипа это последний кадр предыдущего. Модель продолжает ровно с него.',
            'Объект уходит из кадра так, как нужно следующему клипу: это прописано в конце каждого промпта.',
        ],
        'pitfalls': [
            'Кадр входа бери за 0,3–0,5 с ДО контакта: иначе следующий клип унаследует объект «в диске».',
            'Реф тянет всё, что на нём есть: обрежь референс до нужного объекта и напиши, чего в кадре быть не должно.',
            'Не пиши «никто не пострадал» в каждом звене слишком настойчиво: цепь должна расти (искры, огонь, вода, толпа).',
            'Модель иногда меняет технику (троллейбус → трамвай). Эпохе не мешает, не перегенерируй.',
        ],
        'source': SOURCE + 'сентябрь и октябрь 2026, «Эффект бабочки» 1–3',
        'steps': [
            {
                'title': 'Клип 1', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 8,
                'prompt': '''REFERENCES: @Image1 and @Image2 are the hero's face, keep identity exact. @Image3 is his exact outfit, copy it exactly.
LOOK: {{look}} One continuous shot, vertical, no captions, no readable text.
LOCATION: {{place}}.
0-3s: {{hero}} {{trigger}}. He does not look back. Camera: handheld medium shot.
3-6s: the camera follows the thrown object in the air; show the nearest passer-by in the background reacting to nothing yet.
6-8s: {{link1}}. FINAL FRAME: the moment half a second BEFORE contact. Cut before impact.
RULES: exactly one hero, he never looks back. The chain begins but no destruction yet.
AUDIO: ambience, one clear sound for the thrown object. No music.''',
            },
            {
                'title': 'Клип 2 (референс: последний кадр клипа 1)', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 8,
                'prompt': '''@Image1 is the ENTRY FRAME: the first frame of this shot must match it exactly. Continue from this exact moment.
LOOK: {{look}} Same place, same light, same objects. Vertical, no readable text.
0-3s: the collision from the entry frame happens. {{link1}}.
3-6s: {{link2}}. Camera: whip-pan following the moving object.
6-8s: the object leaves the frame heading toward the hero's side of the street. FINAL FRAME: half a second before the next contact. Cut.
RULES: the hero does not appear in this clip. Nobody is hurt. Each object leaves the frame the way the next clip needs.
AUDIO: crash, ambience. No music.''',
            },
            {
                'title': 'Клип 3 (референс: последний кадр клипа 2)', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 8,
                'prompt': '''@Image1 is the ENTRY FRAME: the first frame must match it exactly. Continue from this moment. @Image2 and @Image3 (if supplied) are the hero's face and outfit.
LOOK: {{look}} Same place, same light, same objects. Vertical, no readable text.
0-4s: {{finale}}.
4-7s: the hero reacts, finally understanding what he started. Close-up of his face.
7-8s: freeze on his face.
RULES: exactly one hero, nobody is hurt, no readable text.
AUDIO: impact, silence for a beat, one sigh. No music.''',
            },
        ],
    },
    {
        'id': 'kid-in-game',
        'title': 'Вбежал в игру',
        'emoji': '🎮',
        'family': 'Тренд',
        'kind': 'one_take',
        'difficulty': 'средне',
        'hook': 'Ребёнок играет на диване, вдруг срывается и прыгает в экран телевизора. Камера влетает вместе с ним в игровой мир, где он побеждает всех.',
        'duration': 15,
        'aspect_ratio': '9:16',
        'resolution': '720p',
        'audio': True,
        'looks': ['phone', 'cartoon'],
        'ref_slots': [
            {'n': 1, 'role': 'Лицо героя (только лицо)', 'required': True, 'note': 'Одежду с этого фото игнорировать.'},
            {'n': 2, 'role': 'Герой в домашней одежде', 'required': True, 'note': 'Одежда на весь ролик.'},
            {'n': 3, 'role': 'Комната с телевизором', 'required': True, 'note': 'Ролик начинается в вашей комнате.'},
            {'n': 4, 'role': 'Скрины игрового мира', 'required': False, 'note': 'Только скриншоты, не видео с экрана.'},
        ],
        'fields': [
            {'key': 'hero', 'label': 'Герой', 'default': 'the boy from @Image1 and @Image2'},
            {'key': 'world', 'label': 'Игровой мир', 'default': 'a bright blocky sandbox-style world with saturated green checkered ground and pastel low-poly buildings'},
            {'key': 'win', 'label': 'Надпись победы', 'default': 'ПОБЕДА!'},
        ],
        'beats': [
            {'t': '0–3 с', 'text': 'Герой скучает с геймпадом, вскакивает.'},
            {'t': '3–6 с', 'text': 'Бежит к телевизору и ныряет в экран, камера влетает следом, без склейки.'},
            {'t': '6–12 с', 'text': 'Весь кадр это игра; монстры, удар с аурой, монеты.'},
            {'t': '12–15 с', 'text': 'Камера обходит спереди, надпись победы, большой палец, заморозка.'},
        ],
        'why': [
            'Ролик начинается у вас дома, и в этом «вау».',
            'Один непрерывный кадр: камера бежит за героем и влетает в экран вместе с ним.',
            'Внутри игры запрещена рамка телевизора, иначе игра окажется «на экране», а не вокруг героя.',
        ],
        'pitfalls': [
            'Слово «cut» или «hard cut» в промпте это настоящая склейка. Пиши «one continuous unbroken shot».',
            'Видео-реф с экрана тянет рамку ТВ: давай только скриншоты и запрещай TV frame/bezel.',
            'Реф лица тянет одежду: пиши «only the face, ignore the hoodie» и давай отдельное фото в домашней одежде.',
            'Запрети превращение героя в игрового аватара.',
            'Название и логотип игры не нужны: узнают по миру и врагам.',
        ],
        'source': SOURCE + 'октябрь 2026, ролик «Вбежал в игру»',
        'steps': [
            {
                'title': 'Видео', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 15,
                'prompt': '''REFERENCES: @Image1 and @Image2 are used ONLY for the hero's face; ignore any clothes in them. @Image3 is the exact living room, keep layout identical. @Image4 is the game world look. Hero: {{hero}}, the same clothes and face in every shot, exactly one hero.
LOOK: {{look}} ONE CONTINUOUS UNBROKEN SHOT with no cuts, no edits: the camera physically follows the hero through the TV screen into the game.
THE GAME: {{world}}. Generic game look, no real logos or brand names.
BEAT 1 (0-3s): handheld shot beside the sofa. The hero slumps with a controller watching his avatar chased by round cartoon monsters on the TV. He sits up, grins, tosses the controller and jumps up.
BEAT 2 (3-6s): the camera chases him from behind. He sprints at the TV and dives into the screen: the glass ripples like liquid, neon pixel blocks splash outward. The camera rushes through the screen in the same shot; for a moment the frame is a tunnel of colourful blocks, then it opens inside the game world. No cut, no black frame.
BEAT 3 (6-12s): the ENTIRE frame is the game world edge to edge. There is NO television, NO screen frame, NO living room and NO dark border from now on. Third-person game camera behind him. Five cartoon monsters charge; he dodges, punches, a golden shockwave blasts from his fists, monsters pop into coloured blocks and coins. The hero stays a real photoreal person in his own clothes, never turns into an avatar.
BEAT 4 (12-15s): the camera swings to his front, big chunky text "{{win}}" pops up with confetti, he grins at the camera and gives a thumbs up. Freeze on the grin.
AUDIO: room tone and muffled game sounds, a glassy whoomp when he enters the screen, then bright 8-bit music and a victory jingle. No speech.
NEGATIVE: no extra people, no changed face, no changed clothes, no logos, no TV frame or bezel inside the game, no transformation of the hero.''',
            },
        ],
    },
    {
        'id': 'outfit-whirl',
        'title': 'Смена образов в вихре',
        'emoji': '🌀',
        'family': 'Тренд',
        'kind': 'one_take',
        'difficulty': 'средне',
        'hook': 'Камера смотрит строго сверху. Герой лежит на ковре, надевает маску, вихрь меняет образ пять раз, а в конце маска слетает на кота.',
        'duration': 20,
        'aspect_ratio': '9:16',
        'resolution': '720p',
        'audio': True,
        'looks': ['phone', 'cartoon'],
        'ref_slots': [
            {'n': 1, 'role': 'Лицо героя анфас (только лицо)', 'required': True, 'note': 'Одежду описываем словами, иначе реф тянет свою.'},
            {'n': 2, 'role': 'Лицо героя в профиль', 'required': False, 'note': ''},
        ],
        'fields': [
            {'key': 'hero', 'label': 'Герой', 'default': HERO},
            {'key': 'pet', 'label': 'Кот или питомец', 'default': 'a fluffy grey cat'},
            {'key': 'outfits', 'label': 'Образы (5, по одному на бит)', 'default': 'a 1990s raspberry jacket with gold chain; a white tuxedo with a bow tie; a floor-length leopard fur coat; a gold sequin disco suit; a taxi driver uniform'},
        ],
        'beats': [
            {'t': '0–4 с', 'text': 'Герой в пижаме, берёт маску и надевает на лицо.'},
            {'t': '4–16,5 с', 'text': 'Пять образов подряд, каждый после одного и того же вихря.'},
            {'t': '16,5–20 с', 'text': 'Маска слетает на кота, кот смотрит в камеру. Заморозка.'},
        ],
        'why': [
            'Камера прибита сверху: облёт убивает эффект заморозки.',
            'Вентилятор в кадре мотор сцены: он треплет ткань и «раздувает» вихрь на каждой смене.',
            'Один и тот же вихрь на все переходы, тело возвращается в ту же позу.',
        ],
        'pitfalls': [
            'Слова «cut» и «hard cut» в промпте дают настоящую склейку.',
            'Без вентилятора ткань «мёртвая», кадр выглядит как слайд-шоу.',
            'Финал с котом лучше снимать отдельным клипом от последнего кадра первого.',
            'Из фото берём только лицо, одежду описываем текстом.',
        ],
        'source': SOURCE + 'октябрь 2026, ролик «Тренд: Зелёный»',
        'steps': [
            {
                'title': 'Видео', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 20,
                'prompt': '''REFERENCES: @Image1 and @Image2 are used ONLY for the hero's face; do not copy any clothes. Exactly one person in the film.
LOOK: {{look}} 20 seconds, ONE CONTINUOUS SHOT from a LOCKED overhead camera looking straight down. No pan, no tilt, no zoom, no orbit, no shake, no cuts, no dissolves.
WORLD LOCK (seen from above): a large deep-red patterned rug fills the frame. {{hero}} lies on his back across it, head to the left, feet to the right. At the left edge stands a chrome floor fan, blades spinning, always aimed along the rug at him. At the right edge {{pet}} lies curled up, awake. The rug, fan, pet and framing are identical in every frame; a constant breeze ripples his clothes.
BEAT 1 (0-2.5s): rumpled grey pyjamas, bored stare into the camera, the breeze flutters his collar.
BEAT 2 (2.5-4s): he pulls a glossy plain mask into frame and presses it on his face. The fan roars, the mask flashes and is sucked into his skin, and his body spins into a quick blurred whirlwind of golden dust.
TRANSITION RULE: every outfit change is the same gag: the fan roars, his body spins in place for about four frames, and stops instantly in the next outfit, always landing in the same pose in the same spot.
BEATS 3-7 (4-16.5s): five outfits in order, about three seconds each, face tinted green throughout: {{outfits}}. Each outfit has one signature gesture.
BEAT 8 (16.5-20s): the fan surges and the mask tears off and skitters to the pet, slapping onto its face. The pet sits up wearing the mask, looks into the camera and blinks once. The hero lowers his head in defeat. Freeze on the pet.
AUDIO: constant fan hum, a swing-style brass loop, a comic whoosh on every whirlwind, one lazy meow. No speech.
NEGATIVE: no camera movement, no second person, no changed facial structure, no text, no logos, no harm to the animal.''',
            },
        ],
    },
    {
        'id': 'product-ad',
        'title': 'Реклама продукта 10 с',
        'emoji': '🥫',
        'family': 'Реклама',
        'kind': 'one_take',
        'difficulty': 'просто',
        'hook': 'Три плана за 10 секунд: общий, макро, герой-шот продукта. Без лиц и без читаемого текста. Бриф можно отдать любой LLM, а промпт вставить как есть.',
        'duration': 10,
        'aspect_ratio': '9:16',
        'resolution': '720p',
        'audio': True,
        'looks': ['film'],
        'ref_slots': [
            {'n': 1, 'role': 'Продукт (без надписей)', 'required': False, 'note': 'Чистая банка или упаковка без этикеток.'},
        ],
        'fields': [
            {'key': 'product', 'label': 'Продукт', 'default': 'a plain blue-and-white tin can of sweetened condensed milk'},
            {'key': 'setting', 'label': 'Обстановка', 'default': 'a warm kitchen at dawn, dark wooden table, window light'},
            {'key': 'extra', 'label': 'Деталь на столе', 'default': 'torn bread crust and a steaming mug'},
        ],
        'beats': [
            {'t': '0–4 с', 'text': 'Медленный наезд на стол, продукт в луче света.'},
            {'t': '4–7 с', 'text': 'Макро: ложка поднимает продукт, густая лента стекает обратно.'},
            {'t': '7–10 с', 'text': 'Подъём камеры с дугой, продукт в геройской позиции.'},
        ],
        'why': [
            'Три плана за 10 секунд (общий, макро, герой-шот) держат внимание лучше одного.',
            'Один непрерывный бриф даёт сравнимые результаты у разных LLM, а наши правила промпта сами проверяют ограничения.',
        ],
        'pitfalls': [
            '«no readable text» мало: Seedance всё равно рисует этикетки. Пиши прямо: «plain can, NO label, NO text, blank metal».',
            'Модель, которая пишет «аппетитнее», чаще нарушает ограничения: проверяй кадры по сетке, а не на скорости.',
        ],
        'source': SOURCE + 'октябрь 2026, ролик «Claude против GPT»',
        'steps': [
            {
                'title': 'Видео', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 10,
                'prompt': '''LOOK: {{look}}
Product: {{product}} with NO label, NO text, NO logo, blank metal surface. @Image1 (if supplied) is the exact product to copy. No faces, no people.
Setting: {{setting}}. Also on the table: {{extra}}.
Shot 1 (0-4s): slow dolly-in across the table; the product sits half in a shaft of light, condensation beads on its lid.
Shot 2 (4-7s): low-angle macro, a spoon lifts the thick product and a glossy ribbon folds slowly back, shallow depth of field.
Shot 3 (7-10s): the camera rises and arcs around the product in hero position, soft light flare through the window. End on the product.
AUDIO: spoon tap, slow pour, quiet room tone, one warm piano note at the end.''',
            },
        ],
    },
    {
        'id': 'bench-gag',
        'title': 'Меня грабят, но сначала досмотрю',
        'emoji': '📱',
        'family': 'Тренд',
        'kind': 'two_step',
        'difficulty': 'просто',
        'hook': 'Герой залип в телефон на лавке. Парень в капюшоне уносит рюкзак, возвращается, заглядывает через плечо и садится рядом досматривать.',
        'duration': 12,
        'aspect_ratio': '9:16',
        'resolution': '720p',
        'audio': True,
        'looks': ['phone', 'cartoon'],
        'ref_slots': [
            {'n': 1, 'role': 'Лицо героя анфас', 'required': True, 'note': ''},
            {'n': 2, 'role': 'Лицо героя в профиль', 'required': False, 'note': ''},
            {'n': 3, 'role': 'Старт-кадр (из шага 1)', 'required': True, 'note': 'Одежда уже есть на старт-кадре, отдельный реф одежды не нужен.'},
        ],
        'fields': [
            {'key': 'hero', 'label': 'Герой', 'default': HERO},
            {'key': 'place', 'label': 'Место', 'default': 'a wooden bench at a rainy Minsk bus stop, wet asphalt, yellow leaves'},
        ],
        'beats': [
            {'t': '0–5 с', 'text': 'Парень в капюшоне подходит сзади, берёт рюкзак и уходит из кадра. Герой не реагирует.'},
            {'t': '5–12 с', 'text': 'Парень возвращается с рюкзаком, заглядывает в телефон, садится рядом. Оба смотрят в экран.'},
        ],
        'why': [
            'Один план, без склеек, как будто друг снимает с трёх метров.',
            'Герой не реагирует вообще: «never looks up, never notices, never speaks», вся шутка в этом.',
            'Старт-кадр собран заранее картинкой, локация не плывёт.',
        ],
        'pitfalls': [
            'Подпись ставь в нижнюю треть и не на лицо второго героя.',
            'Сырой кадр из ролика как обложка смотрится случайным: сделай отдельный постер.',
            'Вор может сесть не с той стороны или рюкзак пропадёт к концу. На шутку не влияет.',
        ],
        'source': SOURCE + 'октябрь 2026, ролик «Меня грабят, но сначала…»',
        'steps': [
            {
                'title': 'Шаг 1. Старт-кадр', 'kind': 'image', 'model': 'gpt-image-2', 'aspect_ratio': '9:16',
                'prompt': '''{{look}}
A candid frame from a casual video shot by a friend about 3 metres away, ordinary camera look, slight wide angle, overcast daylight. Location: {{place}}.
Main subject: {{hero}} sits on the right half of the bench, hunched forward, both hands holding a smartphone, eyes on the screen, a slight absorbed half-smile; the screen faces him. Full body visible.
On the bench to his left stands a plain black backpack, clearly his.
In the background about eight metres away a lanky young man in a dark grey hoodie with the hood up walks toward the bench looking at the backpack, small in frame and slightly out of focus.
No text, no logos, no other people.''',
            },
            {
                'title': 'Шаг 2. Видео', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 12,
                'prompt': '''Start exactly from @Image3 as the first frame. The seated man is the man from @Image1 and @Image2: keep face, hair and clothes identical.
LOOK: {{look}} One continuous 12-second take, no cuts, handheld with small natural sway, filmed by a friend from 3 metres away, no slow motion, no music.
WORLD LOCK: same place, same bench, same backpack, same two people only. The seated man never looks up, never notices anything, never speaks; he only scrolls with his thumb and smiles slightly.
Beat 1 (0-5s): the hooded man walks up behind the bench, glances left and right, lifts the backpack by its top handle and walks out of the left edge of the frame.
Beat 2 (5-12s): he walks back in with the backpack, stops behind the seated man's shoulder, leans in to look at the phone, gets curious, sits down close beside him and puts the backpack between them. Both stare at the phone, absorbed. Hold until the end.
AUDIO: quiet ambience, light wind, footsteps, fabric rustle. No speech, no music.''',
            },
        ],
    },
    {
        'id': 'vhs-year',
        'title': 'Кассета VHS: тот самый год',
        'emoji': '📼',
        'family': 'Тренд',
        'kind': 'one_take',
        'difficulty': 'средне',
        'hook': 'Героя «переносят» в конкретный год и город и подают как найденную домашнюю кассету: четыре сцены по 3 секунды и одна фраза «маме» в конце.',
        'duration': 12,
        'aspect_ratio': '9:16',
        'resolution': '720p',
        'audio': True,
        'looks': ['vhs'],
        'ref_slots': [
            {'n': 1, 'role': 'Лицо героя анфас', 'required': True, 'note': 'Причёска должна быть как в нужном году, иначе реф навяжет свою.'},
            {'n': 2, 'role': 'Лицо героя в профиль', 'required': False, 'note': ''},
        ],
        'fields': [
            {'key': 'hero', 'label': 'Герой', 'default': HERO},
            {'key': 'year', 'label': 'Год', 'default': '1986'},
            {'key': 'city', 'label': 'Город', 'default': 'Minsk'},
            {'key': 'styling', 'label': 'Одежда того года', 'default': 'an oversized wool coat, a knitted scarf and a fur ushanka'},
            {'key': 'line', 'label': 'Фраза в камеру', 'default': 'Мам, мы в Минске. Не звони, дорого.'},
        ],
        'beats': [
            {'t': '0–3 с', 'text': 'Улица города того года, герой идёт на камеру.'},
            {'t': '3–6 с', 'text': 'Внутри: аркадные автоматы или магазин, одно действие.'},
            {'t': '6–9 с', 'text': 'Кухня, кафе или такси, одно действие.'},
            {'t': '9–12 с', 'text': 'Ночная улица, герой смотрит в камеру и говорит фразу. Сбой кассеты, синий экран.'},
        ],
        'why': [
            'Один бит на кадр: четыре сцены по 3 секунды, в каждой одно действие, поэтому модель не разваливается на 12 секундах.',
            'Анти-глянец: «interlaced softness, tape noise, auto-zoom pumping», иначе будет чистое кино, а не кассета.',
            'Речь одна короткая фраза, фон на время реплики приглушается.',
        ],
        'pitfalls': [
            'Дату в углу и REC не проси: добавь сам в монтаже (CapCut, моноширинный жёлтый текст).',
            'Если на фото-референсе волосы зачёсаны вверх, модель сделает ирокез, и никакой запрет текстом не спасёт.',
            'Ударение в слове может поплыть: перезапиши реплику озвучкой или выбери фразу без коварных ударений.',
            'Другой год и город меняются только блоком локаций.',
        ],
        'source': SOURCE + 'сентябрь 2026, ролик «Токио ’86»',
        'steps': [
            {
                'title': 'Видео', 'kind': 'video', 'model': 'seedance-2.5', 'duration': 12,
                'prompt': '''REFERENCES: @Image1 and @Image2 are the hero's face, keep identity exact, keep the hairstyle appropriate for the year.
LOOK: {{look}} Home-video footage shot in {{city}}, {{year}}, on a shoulder camcorder by a friend. Real amateur framing, slightly off-centre, small drifts, mono wind rumble. No on-screen text, no date stamp, no subtitles, no logos, no music, no modern objects.
HERO: {{hero}}, wearing {{styling}} authentic to {{year}}. Everyone around wears the fashion of {{year}}.
0-3s: a busy street of {{city}} in {{year}}, period cars and shop signs without readable text. The hero walks toward the camera and points at something.
3-6s: an indoor place typical for {{year}}, lit by period lights. The hero does one simple action and laughs.
6-9s: a cosy interior (a café or a kitchen). The hero does one simple action; a friend behind the camera laughs.
9-12s: a night street, the pavement wet after rain. The hero turns to the camcorder, waves and says in Russian, casually, like a message to his mother, with accurate Russian lip sync: "{{line}}" The last half second: tape glitch, horizontal tearing, a burst of static, the picture drops to blue.
AUDIO: ambience of the street, traffic, rain drips, tape hiss. Briefly lower the street noise while he speaks. Only one spoken line in the whole video.
RULES: exactly one person in frame, faces match @Image1 and @Image2, no text of any kind on screen.''',
            },
        ],
    },
]
