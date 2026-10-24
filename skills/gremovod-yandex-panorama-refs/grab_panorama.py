"""Grab a Yandex panorama from the built-in browser window: crop the viewport, paint out UI and POI marks.

Uses screen pixels only (Pillow, numpy, opencv); nothing is downloaded.

  python grab_panorama.py --thumb C:/Temp/desk.png          # small desktop grab, to find the viewport box
  python grab_panorama.py --out OUT.png --box 1459 225 3178 1123 --save-box
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
DEFAULT_BOX = (1459, 225, 3178, 1123)  # grem's 3840x1600 desktop, detached browser window; recalibrate if layout changes


def load_box():
    if CALIB.is_file():
        return tuple(json.loads(CALIB.read_text(encoding='utf-8'))['box'])
    return DEFAULT_BOX


def paint(crop, extra):
    """Paint out street label, buttons, logo, ground arrows and orange POI marks with captions."""
    h, w = crop.shape[:2]
    mask = np.zeros((h, w), np.uint8)

    def box(x, y, bw, bh):
        mask[max(0, y):min(h, y + bh), max(0, x):min(w, x + bw)] = 255

    box(0, 0, 330, 90)                      # street name, top left
    box(w - 330, 0, 330, 90)                # year, share, menu, close
    box(w - 110, 290, 110, 240)             # zoom +/-
    box(w - 200, h - 80, 200, 80)           # Yandex logo
    box(w // 2 - 190, h - 200, 380, 200)    # ground navigation arrows
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    orange = cv2.inRange(hsv, (8, 120, 200), (22, 255, 255))
    n, _, stats, cent = cv2.connectedComponentsWithStats(orange)
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if 80 < area < 2500:
            box(int(cent[i][0]) - 75, y - 14, 150, 82)
    for bx in extra:
        box(*bx)                            # other POI colours (pink, blue, stars): manual
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8))
    base = cv2.inpaint(crop, mask, 4, cv2.INPAINT_TELEA)
    soft = cv2.GaussianBlur(base, (0, 0), 14)
    alpha = cv2.GaussianBlur(mask.astype(np.float32) / 255, (0, 0), 6)[..., None]
    return (crop * (1 - alpha) + soft * alpha).astype(np.uint8), 100 * (mask > 0).mean()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out')
    ap.add_argument('--box', nargs=4, type=int, metavar=('X0', 'Y0', 'X1', 'Y1'))
    ap.add_argument('--save-box', action='store_true', help='store --box in calibration.json')
    ap.add_argument('--mask', action='append', default=[], help='x,y,w,h in cropped-image coordinates, repeatable')
    ap.add_argument('--crop-left', type=int, default=120, help='cut this many px on the left (another window may cover the edge)')
    ap.add_argument('--thumb', help='save a downscaled desktop grab (to find the box) and exit')
    ap.add_argument('--sheet', nargs='+', help='tile finished images into one sheet for review')
    a = ap.parse_args()

    if a.thumb:
        full = ImageGrab.grab(all_screens=True)
        im = full.copy()
        im.thumbnail((2000, 2000))
        im.save(a.thumb)
        print('thumb', a.thumb, im.size, 'multiply coordinates by', round(full.size[0] / im.size[0], 3))
        return
    if a.sheet:
        ims = [Image.open(p).convert('RGB').resize((860, 480)) for p in a.sheet]
        sheet = Image.new('RGB', (1720, 480 * ((len(ims) + 1) // 2)))
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % 2) * 860, (i // 2) * 480))
        sheet.save(a.out)
        print('sheet', a.out)
        return

    box = tuple(a.box) if a.box else load_box()
    if a.save_box and a.box:
        CALIB.write_text(json.dumps({'box': list(box)}), encoding='utf-8')
    x0, y0, x1, y1 = box
    crop = np.array(ImageGrab.grab(all_screens=True).convert('RGB'))[y0:y1, x0:x1].copy()
    out, pct = paint(crop, [tuple(int(v) for v in m.split(',')) for m in a.mask])
    Image.fromarray(out[:, a.crop_left:]).save(a.out)
    print(a.out, 'size', out.shape[1] - a.crop_left, 'x', out.shape[0], 'painted %.1f%%' % pct)


if __name__ == '__main__':
    sys.exit(main())
