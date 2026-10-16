import io
import unittest
from PIL import Image
from backend import test_smoke, workflow_import


def png():
    stream = io.BytesIO()
    Image.new('RGB', (32, 20), 'red').save(stream, format='PNG')
    return stream.getvalue()


WAV = b'RIFF' + (36).to_bytes(4, 'little') + b'WAVE' + b'fmt ' + bytes(24)


class WorkflowImportTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def upload(self, project, name, content, mime='application/octet-stream'):
        return self.client.post('/api/library/import-reference', data={'project_id': project}, files={'file': (name, content, mime)})

    def test_image_audio_and_documents_become_library_assets(self):
        project = self.client.post('/api/projects', json={'title': 'WF', 'state': {}}).json()['id']
        image = self.upload(project, 'face.PNG', png())
        self.assertEqual(image.status_code, 200, image.text)
        self.assertEqual((image.json()['metadata']['kind'], image.json()['metadata']['width']), ('image', 32))
        self.assertIsNotNone(image.json()['thumbnail_url'])
        audio = self.upload(project, 'voice.wav', WAV)
        self.assertEqual(audio.status_code, 200, audio.text)
        self.assertEqual(audio.json()['metadata']['kind'], 'audio')
        self.assertIsNone(audio.json()['thumbnail_url'])
        note = self.upload(project, 'idea.md', 'Грэм едет по ночному Минску'.encode('utf-8'))
        self.assertEqual(note.status_code, 200, note.text)
        self.assertEqual(note.json()['metadata']['kind'], 'document')
        self.assertIn('Грэм', note.json()['metadata']['excerpt'])
        self.assertIsNone(note.json()['thumbnail_url'])
        pdf = self.upload(project, 'brief.pdf', b'%PDF-1.4\n1 0 obj')
        self.assertEqual(pdf.status_code, 200, pdf.text)
        self.assertNotIn('excerpt', pdf.json()['metadata'])
        self.assertEqual(self.client.get(audio.json()['url']).content, WAV)
        self.assertEqual(self.client.get(f'/api/library/{audio.json()["id"]}/thumbnail').status_code, 404)
        listed = {a['id'] for a in self.client.get('/api/library', params={'project_id': project}).json()}
        self.assertEqual(len(listed), 4)

    def test_rejections(self):
        project = self.client.post('/api/projects', json={'title': 'WF', 'state': {}}).json()['id']
        self.assertEqual(self.upload(project, 'tool.exe', b'MZ').status_code, 400)
        self.assertEqual(self.upload(project, 'fake.mp3', b'not audio at all').status_code, 422)
        self.assertEqual(self.upload(project, 'fake.pdf', b'hello').status_code, 422)
        self.assertEqual(self.upload(project, 'bin.txt', b'ab\x00cd').status_code, 422)
        self.assertEqual(self.upload(project, 'bad.png', b'nope').status_code, 422)
        self.assertEqual(self.upload(project, 'empty.txt', b'').status_code, 400)
        self.assertEqual(self.upload('absent-project', 'a.txt', b'x').status_code, 404)

    def test_document_is_not_accepted_as_image_reference_elsewhere(self):
        project = self.client.post('/api/projects', json={'title': 'WF', 'state': {}}).json()['id']
        doc = self.upload(project, 'idea.txt', b'hello').json()
        self.assertEqual(self.client.get(f'/api/library/{doc["id"]}/analysis').status_code, 404)

    def test_classify(self):
        self.assertEqual(workflow_import.classify('A.M4A')[0], 'audio')
        self.assertEqual(workflow_import.classify('x.srt')[0], 'document')


if __name__ == '__main__':
    unittest.main()
