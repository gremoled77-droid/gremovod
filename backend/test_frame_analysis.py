import io
import unittest
from PIL import Image, ImageDraw
from backend import frame_analysis, test_production


def stripes(vertical=True, size=96):
    image = Image.new('RGB', (size, size), 'white')
    draw = ImageDraw.Draw(image)
    for i in range(0, size, 12):
        draw.rectangle((i, 0, i + 5, size) if vertical else (0, i, size, i + 5), fill='black')
    return image


def diagonals(size=96):
    image = Image.new('RGB', (size, size), 'white')
    draw = ImageDraw.Draw(image)
    for i in range(-size, size * 2, 14):
        draw.line((i, 0, i + size, size), fill='black', width=4)
    return image


class AnalysisMath(unittest.TestCase):
    def test_line_orientation_tone_and_intensity(self):
        vertical = frame_analysis.analyze_image(stripes(True))
        horizontal = frame_analysis.analyze_image(stripes(False))
        diagonal = frame_analysis.analyze_image(diagonals())
        flat = frame_analysis.analyze_image(Image.new('RGB', (96, 96), (128, 128, 128)))
        self.assertEqual(vertical['lines']['dominant'], 'vertical')
        self.assertEqual(horizontal['lines']['dominant'], 'horizontal')
        self.assertEqual(diagonal['lines']['dominant'], 'diagonal')
        self.assertEqual(flat['lines']['dominant'], '')
        self.assertGreater(vertical['tone']['range'], 0.9)
        self.assertLess(flat['tone']['range'], 0.05)
        self.assertGreater(diagonal['visual_intensity'], flat['visual_intensity'])
        self.assertEqual(flat['visual_intensity'], 0)

    def test_color_warm_cool_and_sector(self):
        image = Image.new('RGB', (96, 96), (20, 20, 20))
        ImageDraw.Draw(image).rectangle((64, 0, 95, 31), fill=(255, 140, 0))  # top-right = sector 3
        result = frame_analysis.analyze_image(image)
        self.assertGreater(result['color']['warm'], result['color']['cool'])
        self.assertEqual(result['color']['dominant_hue'], 'оранжевый')
        self.assertEqual(result['attention']['sector'], 3)
        cold = frame_analysis.analyze_image(Image.new('RGB', (96, 96), (30, 80, 200)))
        self.assertGreater(cold['color']['cool'], cold['color']['warm'])

    def test_compare_reports_contrast_on_cut(self):
        a, b = frame_analysis.analyze_image(stripes(True)), frame_analysis.analyze_image(Image.new('RGB', (96, 96), (128, 128, 128)))
        same = frame_analysis.compare(a, a)
        self.assertEqual((same['lines'], same['sector']), (0, 0))
        self.assertGreater(frame_analysis.compare(a, b)['tone'], same['tone'])

    def test_tiny_image_is_rejected(self):
        with self.assertRaises(ValueError):
            frame_analysis.analyze_image(Image.new('RGB', (4, 4)))


class AnalysisApi(unittest.TestCase):
    setUp = test_production.ProductionTests.setUp
    tearDown = test_production.ProductionTests.tearDown
    setup_production = test_production.ProductionTests.setup_production

    def test_endpoints(self):
        self.setup_production()
        base = f'/api/productions/{self.pid}/nodes/{self.char["id"]}'
        stream = io.BytesIO()
        diagonals().save(stream, format='PNG')
        up = self.client.post(base + '/upload', data={'category': '02_Референсы'}, files={'file': ('d.png', stream.getvalue(), 'image/png')})
        self.assertEqual(up.status_code, 200, up.text)
        asset = next(f['asset_id'] for f in self.client.get(base + '/editor').json()['files'] if f.get('asset_id'))
        got = self.client.get(f'/api/library/{asset}/analysis')
        self.assertEqual(got.status_code, 200, got.text)
        self.assertEqual(got.json()['lines']['dominant'], 'diagonal')
        picture = self.client.get(f'/api/library/{asset}/squint')
        self.assertEqual(picture.status_code, 200)
        self.assertEqual(Image.open(io.BytesIO(picture.content)).mode, 'L')
        self.assertEqual(self.client.get('/api/library/missing/analysis').status_code, 404)


if __name__ == '__main__':
    unittest.main()
