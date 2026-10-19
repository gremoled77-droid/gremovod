# Скачать 8 видеоуроков Blackmagic через браузер

Ссылки ведут напрямую на официальные ZIP-архивы. Открывай их в обычном браузере Windows, а не через `curl`: в пользовательском тесте `curl` получал HTML вместо ZIP. Первый архив имеет размер около **3,2 ГБ** по сообщению пользователя. Размеры остальных пока не установлены.

1. [Introduction to Editing — Part 1 (Edit)](https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20250923-xtr312/DaVinci-Resolve-17-Edit-IntroductiontoEditingPart1.zip)
2. [Introduction to Editing — Part 2 (Edit)](https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20211222-xtr312/DaVinci-Resolve-17-Edit-IntroductiontoEditingPart2.zip)
3. [Introduction to Sound Design (Fairlight)](https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20211222-xtr312/DaVinci-Resolve-17-Fairlight-IntroductiontoSoundDesign.zip)
4. [Introduction to Mixing (Fairlight)](https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20211222-xtr312/DaVinci-Resolve-17-Fairlight-IntroductiontoMixing.zip)
5. [Recording VO and ADR (Fairlight)](https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20211222-xtr312/DaVinci-Resolve-17-Fairlight-RecordingVOandADR.zip)
6. [Visual Effects in the Edit Page (Edit)](https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20211222-xtr312/DaVinci-Resolve-17-Edit-VisualEffectsintheEditPage.zip)
7. [Basic Compositing (Fusion)](https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20211222-xtr312/DaVinci-Resolve-17-Fusion-BasicCompositing.zip)
8. [Delivering Content (Color)](https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20220210-xtr313/DaVinci-Resolve-17-Color-DeliveringContent.zip)

После завершения загрузок переместить архивы из папки «Загрузки» в правильные каталоги GremoVOD:

```powershell
cd C:\AI_Workflow_Studio
git pull
py -3 resources\training\davinci_resolve_20\download_videos.py --priority-eight --import-downloads
```

Скрипт только проверяет и перемещает существующие ZIP на локальном диске. Он не качает данные, не распаковывает архивы и не отправляет их на GitHub. Уже правильно размещённые архивы пропускает; нескачанные — отмечает как отсутствующие. Если браузер использует другую папку, укажи `--downloads-dir "D:\Downloads"`.
