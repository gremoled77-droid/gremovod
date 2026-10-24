"""Снимок панорамы Яндекса из окна встроенного браузера: вырезать область панорамы, закрасить интерфейс и отметки.

Только stdlib + Pillow + numpy + opencv. Ничего не скачивает из сети: берёт пиксели с экрана, где панорама уже открыта.

Примеры:
  python grab_panorama.py --thumb C:/Temp/desk.png          # уменьшенный снимок экрана, найти рамку панорамы
  python grab_panorama.py --out OUT.png --box 1459 225 3178 1123
  python grab_panorama.py --out OUT.png --mask 690,85,210,90 --mask 220,325,200,40
  python grab_panorama.py --sheet A.png B.png C.png D.png --out sheet.png
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageGrab

HERE = Path(__file__).resolve().parent
CALIB = HERE / 'calibration.json'
DEFAULT_BOX = (1459, 225, 3178, 1123)  # окно браузера владельца на экране 3840x1600; при другой раскладке перекалибровать


def load_box():
    if CALIB.is_file():
        return tuple(json.loads(CALIB.read_text(encoding='utf-8'))['box'])
    return DEFAULT_BOX


def paint(crop, extra):
    """Закрасить кнопки, подпись улицы, логотип, стрелки и отметки организаций (оранжевые кружки с подписью)."""
    h, w = crop.shape[:2]
    mask = np.zeros((h, w), np.uint8)

    def box(x, y, bw, bh):
        mask[max(0, y):min(h, y + bh), max(0, x):min(w, x + bw)] = 255

    box(0, 0, 330, 90)                      # название улицы, слева сверху
    box(w - 330, 0, 330, 90)                # год, поделиться, меню, закрыть
    box(w - 110, 290, 110, 240)             # масштаб +/-
    box(w - 200, h - 80, 200, 80)           # логотип Яндекса
    box(w // 2 - 190, h - 200, 380, 200)    # стрелки перехода по земле
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    orange = cv2.inRange(hsv, (8, 120, 200), (22, 255, 255))
    n, _, stats, cent = cv2.connectedComponentsWithStats(orange)
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if 80 < area < 2500:
            box(int(cent[i][0]) - 75, y - 14, 150, 82)
    for bx in extra:
        box(*bx)                            # отметки других цветов (розовые, синие, звёздочки): вручную
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8))
    base = cv2.inpaint(crop, mask, 4, cv2.INPAINT_TELEA)
    soft = cv2.GaussianBlur(base, (0, 0), 14)
    alpha = cv2.GaussianBlur(mask.astype(np.float32) / 255, (0, 0), 6)[..., None]
    return (crop * (1 - alpha) + soft * alpha).astype(np.uint8), 100 * (mask > 0).mean()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out')
    ap.add_argument('--box', nargs=4, type=int, metavar=('X0', 'Y0', 'X1', 'Y1'))
    ap.add_argument('--save-box', action='store_true', help='запомнить --box в calibration.json')
    ap.add_argument('--mask', action='append', default=[], help='x,y,w,h в координатах вырезанной картинки; можно несколько')
    ap.add_argument('--crop-left', type=int, default=120, help='срезать слева (другое окно может перекрывать край)')
    ap.add_argument('--thumb', help='сохранить уменьшенный снимок всего экрана (для поиска рамки) и выйти')
    ap.add_argument('--sheet', nargs='+', help='склеить готовые картинки в одну сетку для просмотра')
    a = ap.parse_args()

    if a.thumb:
        im = ImageGrab.grab(all_screens=True)
        im.thumbnail((2000, 2000))
        im.save(a.thumb)
        print('thumb', a.thumb, im.size, '(умножить координаты на', round(ImageGrab.grab(all_screens=True).size[0] / im.size[0], 3), ')')
        return
    if a.sheet:
        ims = [Image.open(p).convert('RGB').resize((860, 480)) for p in a.sheet]
        rows = (len(ims) + 1) // 2
        sheet = Image.new('RGB', (1720, 480 * rows))
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % 2) * 860, (i // 2) * 480))
        sheet.save(a.out)
        print('sheet', a.out)
        return

    box = tuple(a.box) if a.box else load_box()
    if a.save_box and a.box:
        CALIB.write_text(json.dumps({'box': list(box)}), encoding='utf-8')
    im = ImageGrab.grab(all_screens=True).convert('RGB')
    x0, y0, x1, y1 = box
    crop = np.array(im)[y0:y1, x0:x1].copy()
    extra = [tuple(int(v) for v in m.split(',')) for m in a.mask]
    out, pct = paint(crop, extra)
    Image.fromarray(out[:, a.crop_left:]).save(a.out)
    print(a.out, 'размер', out.shape[1] - a.crop_left, 'x', out.shape[0], 'закрашено %.1f%%' % pct)


if __name__ == '__main__':
    sys.exit(main())
