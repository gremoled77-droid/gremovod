"""Звук: библиотека голосов, привязка к героям, звуковые заметки кадров и файлы. Платных вызовов нет."""
import io
import unittest
import uuid
from unittest.mock import AsyncMock, patch

from backend import main
from backend import sound
from backend import test_production as production_tests
from backend import test_storyboard as board_tests


class SoundTests(unittest.TestCase):
    setUp = production_tests.ProductionTests.setUp
    tearDown = production_tests.ProductionTests.tearDown
    setup_production = production_tests.ProductionTests.setup_production
    new = production_tests.ProductionTests.new
    image = board_tests.StoryboardTests.image
    prepare = board_tests.StoryboardTests.prepare

    def voices(self):
        return self.client.get(f'/api/productions/{self.pid}/voices').json()

    def add_voice(self, **extra):
        body = {'provider': 'elevenlabs', 'name': 'Грэм', 'voice_id': 'voice_123', **extra}
        return self.client.post(f'/api/productions/{self.pid}/voices', json=body)

    def test_voice_library_validation_duplicates_and_archive(self):
        self.setup_production()
        ok = self.add_voice(url='https://elevenlabs.io/app/voice-library?voiceId=voice_123', note='основной')
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(self.add_voice().status_code, 409)  # тот же ID того же сервиса
        self.assertEqual(self.add_voice(provider='fish').status_code, 200)  # другой сервис, тот же ID
        for bad in (dict(voice_id='bad id!'), dict(voice_id='x', model='no-such-model'), dict(voice_id='y', url='http://elevenlabs.io/a'),
                    dict(voice_id='z', url='https://evil.test/a'), dict(voice_id='w', name='  '), dict(voice_id='')):
            self.assertIn(self.add_voice(**bad).status_code, (400, 422), bad)
        voices = self.voices()
        self.assertEqual([(v['provider'], v['voice_id']) for v in voices], [('elevenlabs', 'voice_123'), ('fish', 'voice_123')])
        self.assertEqual(voices[0]['model'], 'eleven_multilingual_v2')
        self.assertEqual(voices[1]['model'], 's2.1-pro')
        gone = self.client.delete(f'/api/productions/{self.pid}/voices/{ok.json()["id"]}')
        self.assertEqual(gone.status_code, 200)
        self.assertEqual(len(self.voices()), 1)
        self.assertEqual(self.client.delete(f'/api/productions/{self.pid}/voices/{ok.json()["id"]}').status_code, 404)
        self.assertEqual(self.add_voice().status_code, 200)  # архивный ID можно добавить снова
        self.assertEqual(self.client.get('/api/productions/nope/voices').status_code, 404)

    def test_voice_assignment_writes_character_card_and_can_be_undone(self):
        self.setup_production()
        vid = self.add_voice().json()['id']
        voice_url = f'/api/productions/{self.pid}/voices/{vid}'
        done = self.client.post(voice_url + '/assign', json={'character_node_id': self.char['id']})
        self.assertEqual(done.status_code, 200, done.text)
        card = self.client.get(f'/api/productions/{self.pid}/nodes/{self.char["id"]}/voice').json()
        self.assertEqual((card['voice_id'], card['name'], card['provider']), ('voice_123', 'Грэм', 'elevenlabs'))
        self.assertEqual([a['title'] for a in self.voices()[0]['assigned']], ['Грэм'])
        folder = main.PRODUCTIONS_ROOT / self.char['relative_dir'] / '04_Голос' / 'ГОЛОС.json'
        self.assertIn('voice_123', folder.read_text(encoding='utf-8'))
        # Герой, не принадлежащий проекту, и не-герой отклоняются.
        series = self.new('series', 'Серия')
        self.assertEqual(self.client.post(voice_url + '/assign', json={'character_node_id': series['id']}).status_code, 400)
        self.assertEqual(self.client.post(voice_url + '/assign', json={'character_node_id': 'foreign'}).status_code, 404)
        # Снять можно только свой голос.
        other = self.add_voice(voice_id='other_456', name='Другой').json()['id']
        self.assertEqual(self.client.post(f'/api/productions/{self.pid}/voices/{other}/unassign', json={'character_node_id': self.char['id']}).status_code, 409)
        self.assertEqual(self.client.post(voice_url + '/unassign', json={'character_node_id': self.char['id']}).status_code, 200)
        card = self.client.get(f'/api/productions/{self.pid}/nodes/{self.char["id"]}/voice').json()
        self.assertEqual(card['voice_id'], '')
        self.assertEqual(self.voices()[0]['assigned'], [])

    def test_hero_can_have_several_voices_and_eleven_v4(self):
        self.setup_production()
        first = self.add_voice(model='eleven_v4').json()['id']
        second = self.add_voice(voice_id='voice_456', name='Грэм тихо').json()['id']
        for vid in (first, second):
            self.assertEqual(self.client.post(f'/api/productions/{self.pid}/voices/{vid}/assign', json={'character_node_id': self.char['id']}).status_code, 200)
        self.assertEqual([[a['title'] for a in v['assigned']] for v in self.voices()], [['Грэм'], ['Грэм']])
        card = f'/api/productions/{self.pid}/nodes/{self.char["id"]}/voice'
        self.assertEqual(self.client.get(card).json()['voice_id'], 'voice_456')  # последний привязанный — по умолчанию
        self.client.post(f'/api/productions/{self.pid}/voices/{second}/unassign', json={'character_node_id': self.char['id']})
        shown = self.client.get(card).json()
        self.assertEqual((shown['voice_id'], shown['model']), ('voice_123', 'eleven_v4'))  # по умолчанию вернулся первый голос
        self.assertEqual(self.voices()[1]['assigned'], [])

    def test_voice_preview_uses_free_voice_lookup_and_only_elevenlabs(self):
        self.setup_production()
        eleven = self.add_voice().json()['id']
        fish = self.add_voice(provider='fish').json()['id']
        url = f'/api/productions/{self.pid}/voices/'
        with patch.object(sound, 'fetch_preview', AsyncMock(return_value='https://cdn.example.test/p.mp3')) as fetch,                 patch.object(main, 'provider_key', return_value='k'):
            ok = self.client.get(url + eleven + '/preview')
            self.assertEqual((ok.status_code, ok.json()), (200, {'preview_url': 'https://cdn.example.test/p.mp3'}))
            fetch.assert_awaited_once_with('voice_123', 'k')
            self.assertEqual(self.client.get(url + fish + '/preview').status_code, 400)
            self.assertEqual(self.client.get(url + 'nope/preview').status_code, 404)

    def cue(self, frame, **extra):
        body = {'kind': 'sfx', 'text': 'хлопок двери', **extra}
        return self.client.post(f'/api/productions/{self.pid}/nodes/{frame}/sound', json=body)

    def board_frame(self):
        board = self.prepare()
        _, done = board_tests.StoryboardTests.send(self, board, scene_title='Двор', frames=[{'asset_id': self.image('green'), 'title': 'Общий'}])
        self.assertEqual(done.status_code, 200, done.text)
        return done.json()['frame_ids'][0]

    def test_cues_have_default_levels_validate_hero_and_summarize_by_series(self):
        frame = self.board_frame()
        defaults = {'voice': 0.0, 'ambience': -20.0, 'sfx': -6.0, 'music': -12.0}
        for kind, level in defaults.items():
            extra = {'hero_node_id': self.char['id']} if kind == 'voice' else {}
            made = self.cue(frame, kind=kind, text='т', **extra)
            self.assertEqual(made.status_code, 200, made.text)
            self.assertEqual(made.json()['level_db'], level, kind)
        self.assertEqual(self.cue(frame, kind='voice').status_code, 400)  # реплике нужен герой
        self.assertEqual(self.cue(frame, kind='voice', hero_node_id='foreign').status_code, 400)
        self.assertEqual(self.cue(frame, level_db=99).status_code, 422)
        self.assertEqual(self.cue(frame, start_s=-1).status_code, 422)
        self.assertEqual(self.cue(self.series['id']).status_code, 404)  # заметки только у кадров
        data = self.client.get(f'/api/productions/{self.pid}/series/{self.series["id"]}/sound').json()
        self.assertEqual(len(data), 1)
        self.assertEqual([c['kind'] for c in data[0]['cues']], ['voice', 'ambience', 'sfx', 'music'])
        self.assertTrue(all(c['status'] == 'plan' for c in data[0]['cues']))
        self.assertEqual(self.client.get(f'/api/productions/{self.pid}/series/wrong/sound').status_code, 404)

    def test_cue_update_archive_and_files(self):
        frame = self.board_frame()
        cid = self.cue(frame, text='дождь', kind='ambience').json()['id']
        url = f'/api/productions/{self.pid}/sound/{cid}'
        body = {'kind': 'ambience', 'text': 'сильный дождь', 'level_db': -18, 'start_s': 0.5, 'duration_s': 4}
        self.assertEqual(self.client.put(url, json=body).status_code, 200)
        self.assertEqual(self.client.put(url, json={**body, 'kind': 'sfx'}).status_code, 400)  # тип не меняется
        up = self.client.post(url + '/file', files={'file': ('rain.mp3', b'ID3fake-audio', 'audio/mpeg')})
        self.assertEqual(up.status_code, 200, up.text)
        self.assertEqual(self.client.post(url + '/file', files={'file': ('x.png', b'png', 'image/png')}).status_code, 415)
        self.assertEqual(self.client.post(url + '/file', files={'file': ('e.wav', b'', 'audio/wav')}).status_code, 400)
        cue = self.client.get(f'/api/productions/{self.pid}/series/{self.series["id"]}/sound').json()[0]['cues'][0]
        self.assertEqual((cue['text'], cue['level_db'], cue['start_s'], cue['duration_s'], cue['status']), ('сильный дождь', -18, 0.5, 4, 'file'))
        self.assertEqual(cue['filename'], 'rain.mp3')
        stored = main.PRODUCTIONS_ROOT / next(f['relative_path'] for f in self.client.get(f'/api/productions/{self.pid}/nodes/{frame}').json()['files'] if f['kind'] == 'audio')
        self.assertTrue(stored.is_file())
        self.assertEqual(self.client.get(cue['url']).status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertEqual(self.client.get(f'/api/productions/{self.pid}/series/{self.series["id"]}/sound').json()[0]['cues'], [])
        self.assertTrue(stored.is_file())  # файл остаётся в папке кадра
        self.assertEqual(self.client.delete(url).status_code, 404)

    def test_link_generated_audio_and_csv_list(self):
        frame = self.board_frame()
        cid = self.cue(frame, kind='voice', text='Куда едем?', hero_node_id=self.char['id']).json()['id']
        # Звук из библиотеки (как после озвучки реплики) привязывается и копируется в папку кадра.
        fid = uuid.uuid4().hex
        (main.LIBRARY_ROOT / (fid + '.mp3')).write_bytes(b'ID3fake')
        import json as _json
        with main.connect() as db:
            db.execute('INSERT INTO library_assets VALUES(?,?,?,?,?,?,?,?)', (fid, 'job-' + fid, self.project, 0, fid + '.mp3', '',
                       _json.dumps({'kind': 'audio', 'provider': 'fish'}), main.now()))
        url = f'/api/productions/{self.pid}/sound/{cid}/link-asset'
        self.assertEqual(self.client.post(url, json={'asset_id': 'missing'}).status_code, 404)
        image = self.image('red')  # картинка не годится как звук
        self.assertEqual(self.client.post(url, json={'asset_id': image}).status_code, 400)
        linked = self.client.post(url, json={'asset_id': fid})
        self.assertEqual(linked.status_code, 200, linked.text)
        cue = self.client.get(f'/api/productions/{self.pid}/series/{self.series["id"]}/sound').json()[0]['cues'][0]
        self.assertEqual(cue['status'], 'file')
        csv = self.client.get(f'/api/productions/{self.pid}/series/{self.series["id"]}/sound-list')
        self.assertEqual(csv.status_code, 200)
        text = csv.content.decode('utf-8-sig')
        self.assertIn('Сцена;Кадр;Тип;Текст;Герой', text.splitlines()[0])
        self.assertIn('1. Двор;1.1 Общий;Реплика;Куда едем?;Грэм;0.0;0.0;;', text)
        self.assertIn('файл есть', text)
        self.assertEqual(self.client.get(f'/api/productions/{self.pid}/series/nope/sound-list').status_code, 404)


if __name__ == '__main__':
    unittest.main()
