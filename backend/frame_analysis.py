"""Local frame analysis (no provider calls, no cost): tone, colour, line orientation, attention sector, sharpness.

Heuristics after Bruce Block's visual components; numbers are estimates meant for comparison between shots."""
import colorsys
import io
import json
import math

from fastapi import HTTPException
from fastapi.responses import Response

SIZE = 96
HUE_NAMES = ['красный', 'оранжевый', 'жёлтый', 'зелёный', 'голубой', 'синий', 'фиолетовый', 'пурпурный']


def _percentile(sorted_values, q):
    return sorted_values[min(len(sorted_values) - 1, int(q * len(sorted_values)))]


def analyze_image(image):
    """image: PIL image. Returns a dict of metrics; raises ValueError for unusable input."""
    from PIL import ImageOps
    image = ImageOps.exif_transpose(image).convert('RGB')
    image.thumbnail((SIZE, SIZE))
    w, h = image.size
    if w < 8 or h < 8:
        raise ValueError('Изображение слишком маленькое для анализа')
    pixels = list(image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata())
    gray = [int(0.299 * r + 0.587 * g + 0.114 * b) for r, g, b in pixels]
    ordered = sorted(gray)
    p5, p95 = _percentile(ordered, 0.05), _percentile(ordered, 0.95)
    tonal_range = (p95 - p5) / 255
    n = len(gray)
    dark, light = sum(1 for v in gray if v < 85) / n, sum(1 for v in gray if v > 170) / n
    # Colour: saturation, warm/cool shares, hue histogram of saturated pixels.
    sat_sum, warm, cool, colored = 0.0, 0, 0, 0
    hue_bins = [0] * 8
    for r, g, b in pixels:
        hh, ss, vv = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        sat_sum += ss
        if ss > 0.2 and vv > 0.15:
            colored += 1
            deg = hh * 360
            hue_bins[int(((deg + 22.5) % 360) // 45)] += 1
            if deg < 70 or deg >= 330:
                warm += 1
            elif 150 <= deg <= 270:
                cool += 1
    saturation = sat_sum / n
    # Gradients: orientation of edges (line motif) and local sharpness.
    mag_total = h_lines = v_lines = d_lines = 0.0
    sharp = [[0.0, 0] for _ in range(9)]
    bright = [[0.0, 0.0, 0] for _ in range(9)]
    for y in range(h):
        for x in range(w):
            sector = min(2, y * 3 // h) * 3 + min(2, x * 3 // w)
            v = gray[y * w + x]
            bright[sector][0] += v
            bright[sector][1] += v * v
            bright[sector][2] += 1
            if 0 < x < w - 1 and 0 < y < h - 1:
                gx = gray[y * w + x + 1] - gray[y * w + x - 1]
                gy = gray[(y + 1) * w + x] - gray[(y - 1) * w + x]
                mag = math.hypot(gx, gy)
                lap = abs(4 * v - gray[y * w + x - 1] - gray[y * w + x + 1] - gray[(y - 1) * w + x] - gray[(y + 1) * w + x])
                sharp[sector][0] += lap
                sharp[sector][1] += 1
                if mag > 24:
                    mag_total += mag
                    angle = math.degrees(math.atan2(abs(gy), abs(gx)))  # 0 = vertical edge, 90 = horizontal edge
                    if angle < 20:
                        v_lines += mag
                    elif angle > 70:
                        h_lines += mag
                    else:
                        d_lines += mag
    edge_density = mag_total / (n * 255)
    shares = {'vertical': v_lines / mag_total if mag_total else 0, 'horizontal': h_lines / mag_total if mag_total else 0,
              'diagonal': d_lines / mag_total if mag_total else 0}
    if mag_total == 0:
        line = ''
    elif shares['diagonal'] >= 0.45:
        line = 'diagonal'
    elif max(shares['vertical'], shares['horizontal']) >= 0.5:
        line = 'vertical' if shares['vertical'] >= shares['horizontal'] else 'horizontal'
    else:
        line = 'mixed'
    # 3x3 attention: brightest, most contrasting, estimate = both plus saturation-free luminance weight.
    means = [b[0] / b[2] if b[2] else 0 for b in bright]
    contrast = [math.sqrt(max(0, b[1] / b[2] - (b[0] / b[2]) ** 2)) if b[2] else 0 for b in bright]
    top_mean, top_contrast = max(means) or 1, max(contrast) or 1
    attention_score = [0.5 * means[i] / top_mean + 0.5 * contrast[i] / top_contrast for i in range(9)]
    sharpness = [s[0] / s[1] if s[1] else 0 for s in sharp]
    top_sharp = max(sharpness) or 1
    blur_share = sum(1 for s in sharpness if s < 0.25 * top_sharp) / 9
    dominant = max(range(8), key=lambda i: hue_bins[i]) if colored else None
    warm_cool = {'warm': warm / n, 'cool': cool / n}
    tone_hint = 'conceal' if dark > 0.45 and tonal_range < 0.75 else ('reveal' if tonal_range >= 0.35 else '')
    intensity = 0.34 * tonal_range + 0.2 * min(1, saturation / 0.6) + 0.26 * shares['diagonal'] + 0.2 * min(1, edge_density / 0.25)
    return {
        'size': [w, h],
        'tone': {'range': round(tonal_range, 3), 'mean': round(sum(gray) / n / 255, 3), 'dark_share': round(dark, 3), 'light_share': round(light, 3),
                 'hint': tone_hint},
        'color': {'saturation': round(saturation, 3), 'warm': round(warm_cool['warm'], 3), 'cool': round(warm_cool['cool'], 3),
                  'dominant_hue': HUE_NAMES[dominant] if dominant is not None else '', 'hue_bins': hue_bins},
        'lines': {'dominant': line, 'shares': {k: round(v, 3) for k, v in shares.items()}, 'edge_density': round(edge_density, 3)},
        'attention': {'brightest_sector': means.index(max(means)) + 1, 'contrast_sector': contrast.index(max(contrast)) + 1,
                      'sector': attention_score.index(max(attention_score)) + 1},
        'focus': {'blur_share': round(blur_share, 3), 'sharpness': [round(s, 1) for s in sharpness],
                  'hint': 'мягкий фон/размытие: пространство читается плоским' if blur_share >= 0.5 else ''},
        'visual_intensity': max(0, min(10, round(intensity * 10))),
    }


def compare(a, b):
    """Contrast between two analyses 0..1 per component; high values mean a visible change on the cut."""
    return {
        'tone': round(abs(a['tone']['mean'] - b['tone']['mean']) + abs(a['tone']['range'] - b['tone']['range']) / 2, 3),
        'saturation': round(abs(a['color']['saturation'] - b['color']['saturation']), 3),
        'warmth': round(abs((a['color']['warm'] - a['color']['cool']) - (b['color']['warm'] - b['color']['cool'])), 3),
        'lines': 0 if a['lines']['dominant'] == b['lines']['dominant'] else 1,
        'sector': 0 if a['attention']['sector'] == b['attention']['sector'] else 1,
    }


def register(app, studio):
    def source(asset_id):
        from PIL import Image
        studio.checked_id(asset_id)
        with studio.connect() as db:
            row = db.execute('SELECT * FROM library_assets WHERE id=?', (asset_id,)).fetchone()
        if not row or json.loads(row['metadata']).get('kind') in {'video', 'audio'}:
            raise HTTPException(404, 'Изображение для анализа не найдено')
        path = (studio.LIBRARY_ROOT / row['filename']).resolve()
        if not path.is_relative_to(studio.LIBRARY_ROOT.resolve()) or not path.is_file():
            raise HTTPException(404, 'Файл изображения отсутствует')
        try:
            image = Image.open(path)
            image.load()
        except Exception:
            raise HTTPException(400, 'Файл не удалось прочитать как изображение')
        return image

    @app.get('/api/library/{asset_id}/analysis')
    def analysis(asset_id: str):
        try:
            return analyze_image(source(asset_id))
        except ValueError as error:
            raise HTTPException(400, str(error))

    @app.get('/api/library/{asset_id}/squint')
    def squint(asset_id: str):
        from PIL import ImageFilter, ImageOps
        image = ImageOps.exif_transpose(source(asset_id)).convert('L')
        image.thumbnail((640, 640))
        image = ImageOps.autocontrast(image.filter(ImageFilter.GaussianBlur(max(2, image.width // 60))), cutoff=2)
        out = io.BytesIO()
        image.save(out, format='PNG')
        return Response(out.getvalue(), media_type='image/png', headers={'Cache-Control': 'no-store'})
