"""Persistent storyboard import: real folders in temporary storage, no provider calls."""
import uuid
from pathlib import Path
from backend import main
from backend import test_production as production_tests
import unittest


class StoryboardTests(unittest.TestCase):
    setUp=production_tests.ProductionTests.setUp
    tearDown=production_tests.ProductionTests.tearDown
    setup_production=production_tests.ProductionTests.setup_production
    new=production_tests.ProductionTests.new

    def prepare(self):
        self.setup_production()
        self.series=self.new('series','Дорожная история')
        self.path=f'/api/productions/{self.pid}/series/{self.series["id"]}/storyboard'
        return self.client.get(self.path).json()

    def body(self,board,text='Сцена 1 — Встреча\nГрэм: Куда едем?\nСцена 2 — Поездка\nГость отвечает.'):
        return {'script':text,'base_revision':board['revision'],'request_id':uuid.uuid4().hex}

    def test_import_persists_nodes_source_files_and_idempotency(self):
        board=self.prepare();body=self.body(board)
        preview=self.client.post(self.path+'/preview',json=body)
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertEqual(len(preview.json()['scenes']),2)
        self.assertFalse(self.client.get(self.path).json()['scenes'])
        result=self.client.post(self.path+'/import',json=body)
        self.assertEqual(result.status_code,200,result.text)
        saved=self.client.get(self.path).json()
        self.assertEqual(saved['script'],body['script'])
        self.assertEqual([s['number'] for s in saved['scenes']],[1,2])
        self.assertEqual(saved['scenes'][0]['notes'],'Грэм: Куда едем?')
        self.assertNotEqual(saved['revision'],board['revision'])
        for scene in saved['scenes']:
            self.assertTrue((main.PRODUCTIONS_ROOT/scene['relative_dir']/'01_Сценарий/СЦЕНА.md').is_file())
        self.assertTrue(self.client.post(self.path+'/import',json=body).json()['replayed'])
        self.assertEqual(len(self.client.get(self.path).json()['scenes']),2)
        altered={**body,'script':'Сцена 1 — Другая\nНовый текст.'}
        self.assertEqual(self.client.post(self.path+'/import',json=altered).status_code,409)

    def test_stale_board_duplicate_titles_and_cross_production_rejected(self):
        board=self.prepare();body=self.body(board)
        self.new('episode','Существующая',self.series['id'])
        self.assertEqual(self.client.post(self.path+'/import',json=body).status_code,409)
        current=self.client.get(self.path).json()
        duplicate=self.body(current,'Сцена 1 — Существующая\nНе заменять.')
        self.assertEqual(self.client.post(self.path+'/preview',json=duplicate).json()['conflicts'],['Существующая'])
        self.assertEqual(self.client.post(self.path+'/import',json=duplicate).status_code,409)
        wrong=self.path.replace(self.pid,'wrong-project')
        self.assertEqual(self.client.get(wrong).status_code,404)
        self.assertEqual(self.client.post(wrong+'/import',json=body).status_code,404)

    def test_disk_conflict_rolls_back_all_new_scenes(self):
        board=self.prepare();body=self.body(board)
        existing=main.PRODUCTIONS_ROOT/self.series['relative_dir']/'02_Эпизоды/002_Поездка'
        existing.mkdir()
        result=self.client.post(self.path+'/import',json=body)
        self.assertEqual(result.status_code,409,result.text)
        self.assertFalse(self.client.get(self.path).json()['scenes'])
        self.assertFalse((existing.parent/'001_Встреча').exists())
        self.assertTrue(existing.is_dir())
        with main.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM storyboard_imports').fetchone()[0],0)

    def test_existing_frames_and_files_visible_and_unchanged_on_append(self):
        board=self.prepare()
        scene=self.new('episode','Старый эпизод',self.series['id']);frame=self.new('frame','Рабочий кадр',scene['id'])
        # Existing production upload path supplies a valid PNG and real file linkage.
        from PIL import Image
        import io
        stream=io.BytesIO();Image.new('RGB',(8,8),'blue').save(stream,format='PNG')
        upload=self.client.post(f'/api/productions/{self.pid}/nodes/{frame["id"]}/upload',data={'category':'01_Исходники'},files={'file':('frame.png',stream.getvalue(),'image/png')})
        self.assertEqual(upload.status_code,200,upload.text)
        current=self.client.get(self.path).json()
        self.assertEqual(current['scenes'][0]['frames'][0]['files'][0]['kind'],'image')
        self.assertEqual(self.client.post(self.path+'/import',json=self.body(current)).status_code,200)
        latest=self.client.get(self.path).json()
        self.assertEqual(latest['scenes'][0]['frames'][0]['id'],frame['id'])
        self.assertEqual(self.client.get(upload.json()['url']).content,stream.getvalue())

    def test_bad_input_creates_no_folders(self):
        board=self.prepare()
        for text in ['Текст без заголовков','Сцена 1 — CON\nТекст','Сцена 1 — А\nТекст\nСцена 2 — А\nДругой текст']:
            self.assertEqual(self.client.post(self.path+'/import',json=self.body(board,text)).status_code,400)
        self.assertFalse(self.client.get(self.path).json()['scenes'])

    def test_explicit_update_preserves_frames_ids_and_unmentioned_scenes(self):
        current=self.prepare();body=self.body(current)
        self.assertEqual(self.client.post(self.path+'/import',json=body).status_code,200)
        current=self.client.get(self.path).json();original=current['scenes'][0]
        frame=self.new('frame','Существующий дубль',original['id'])
        current=self.client.get(self.path).json()
        update={**self.body(current,'Сцена 1 — Встреча после правки\nНовая реплика.'),'mode':'update','scene_node_ids':[original['id']]}
        self.assertEqual(self.client.post(self.path+'/import',json=update).status_code,200)
        saved=self.client.get(self.path).json()
        self.assertEqual(len(saved['scenes']),2)
        self.assertEqual(saved['scenes'][0]['id'],original['id'])
        self.assertEqual(saved['scenes'][0]['relative_dir'],original['relative_dir'])
        self.assertEqual(saved['scenes'][0]['frames'][0]['id'],frame['id'])
        self.assertEqual(saved['scenes'][0]['notes'],'Новая реплика.')
        self.assertTrue(self.client.post(self.path+'/import',json=update).json()['replayed'])
        bad={**update,'request_id':uuid.uuid4().hex,'base_revision':saved['revision'],'scene_node_ids':['foreign']}
        self.assertEqual(self.client.post(self.path+'/import',json=bad).status_code,400)

    def order(self,board,parent,ids):
        return self.client.put(self.path+'/order',json={'base_revision':board['revision'],'parent_id':parent,'node_ids':ids})

    def test_reorder_changes_only_numbers_and_rejects_stale_or_foreign_ids(self):
        board=self.prepare()
        self.assertEqual(self.client.post(self.path+'/import',json=self.body(board)).status_code,200)
        board=self.client.get(self.path).json();first,second=board['scenes']
        frames=[self.new('frame',f'Кадр {i}',first['id']) for i in (1,2,3)]
        other=self.new('frame','Чужой кадр',second['id'])
        board=self.client.get(self.path).json()
        # Порядок сцен: меняются только number, папки и ID остаются.
        done=self.order(board,self.series['id'],[second['id'],first['id']])
        self.assertEqual(done.status_code,200,done.text)
        saved=self.client.get(self.path).json()
        self.assertEqual([s['id'] for s in saved['scenes']],[second['id'],first['id']])
        self.assertEqual([s['number'] for s in saved['scenes']],[1,2])
        self.assertEqual([s['relative_dir'] for s in saved['scenes']],[second['relative_dir'],first['relative_dir']])
        self.assertTrue((main.PRODUCTIONS_ROOT/first['relative_dir']).is_dir())
        self.assertEqual(done.json()['revision'],saved['revision'])
        # Устаревшая ревизия не применяется.
        self.assertEqual(self.order(board,self.series['id'],[first['id'],second['id']]).status_code,409)
        # Кадры: неполный список ставит названные первыми, остальные следуют в прежнем порядке.
        ids=[f['id'] for f in frames]
        part=self.order(saved,first['id'],[ids[2]])
        self.assertEqual(part.status_code,200,part.text)
        again=self.client.get(self.path).json()
        scene=next(s for s in again['scenes'] if s['id']==first['id'])
        self.assertEqual([f['id'] for f in scene['frames']],[ids[2],ids[0],ids[1]])
        self.assertEqual([f['number'] for f in scene['frames']],[1,2,3])
        # Чужой кадр, повтор и чужой родитель отклоняются.
        for parent,items in [(first['id'],[other['id']]),(first['id'],[ids[0],ids[0]]),('foreign',[ids[0]]),(self.series['id'],[ids[0]])]:
            self.assertEqual(self.order(again,parent,items).status_code,400,(parent,items))
        self.assertEqual(self.client.put(self.path.replace(self.pid,'wrong-project')+'/order',json={'base_revision':again['revision'],'parent_id':first['id'],'node_ids':ids}).status_code,404)
