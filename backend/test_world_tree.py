"""World tree: nested places, place variants and hero looks; only approved images reach a request."""
import io
import unittest
from types import SimpleNamespace
from PIL import Image
from backend import main, production_entities, test_production


class WorldTreeTests(unittest.TestCase):
    setUp=test_production.ProductionTests.setUp
    tearDown=test_production.ProductionTests.tearDown
    setup_production=test_production.ProductionTests.setup_production
    new=test_production.ProductionTests.new

    def post_node(self,**body):
        return self.client.post(f'/api/productions/{self.pid}/nodes',json=body)

    def image(self,node,color):
        content=io.BytesIO();Image.new('RGB',(32,48),color).save(content,format='PNG')
        r=self.client.post(f'/api/productions/{self.pid}/nodes/{node["id"]}/upload',data={'category':'01_Референсы'},files={'file':(color+'.png',content.getvalue(),'image/png')})
        self.assertEqual(r.status_code,200,r.text);return r.json()['id']

    def save(self,node,**data):
        path=f'/api/productions/{self.pid}/nodes/{node["id"]}/editor';editor=self.client.get(path).json()
        body={**editor['data'],'base_revision':editor['revision'],'notes':editor['node']['notes'],**data}
        return self.client.put(path,json=body)

    def context(self,node):
        editor=self.client.get(f'/api/productions/{self.pid}/nodes/{node["id"]}/editor').json()
        return production_entities.context(main,SimpleNamespace(production_id=self.pid,production_node_id=node['id'],project_id=self.project,
                                                                entity_revision=editor['revision'],target='gpt-image-2.5',entity_instruction='x'))

    def test_places_variants_and_looks_nest_in_real_folders(self):
        self.setup_production()
        minsk=self.new('location','Минск');yard=self.new('location','Двор на Немиге',minsk['id'])
        night=self.post_node(kind='location',title='Ночь',parent_id=yard['id'],variant=True).json()
        self.assertEqual(night['variant'],1);self.assertEqual(yard['variant'],0)
        self.assertTrue((main.PRODUCTIONS_ROOT/'GremoVOD'/'02_Локации'/'Минск'/'Двор на Немиге'/'Ночь'/'01_Референсы').is_dir())
        winter=self.new('look','Зима',self.char['id'])
        self.assertTrue((main.PRODUCTIONS_ROOT/self.char['relative_dir']/'05_Образы'/'Зима'/'02_Изображения').is_dir())
        self.assertIsNone(winter['character_id'])
        for wrong in [dict(kind='location',title='Внутри варианта',parent_id=night['id']),dict(kind='location',title='Корень',variant=True),
                      dict(kind='look',title='Образ места',parent_id=yard['id']),dict(kind='look',title='Без героя'),
                      dict(kind='location',title='Место в герое',parent_id=self.char['id'])]:
            self.assertEqual(self.post_node(**wrong).status_code,400,wrong)

    def test_variant_sends_only_its_approved_image_and_place_geometry(self):
        self.setup_production()
        yard=self.new('location','Двор на Немиге');night=self.post_node(kind='location',title='Ночь',parent_id=yard['id'],variant=True).json()
        geometry=self.image(yard,'gray');self.image(yard,'white')  # второй фон двора не утверждён и не должен уйти
        series=self.new('series','Пилот');scene=self.new('episode','Сцена 06',series['id'])
        self.assertEqual(self.save(scene,location_node_id=night['id']).status_code,200)
        result=self.context(scene)
        self.assertEqual(result['references'],[]);self.assertEqual(result['missing_approved'],['Ночь','Двор на Немиге'])
        dark=self.image(night,'black')
        self.assertEqual(self.save(night,selected_image_file_id=dark).status_code,200)
        self.assertEqual(self.save(yard,selected_image_file_id=geometry).status_code,200)
        result=self.context(scene)
        self.assertEqual([(r['role'],r['note']) for r in result['references']],[('location','Ночь'),('location','Двор на Немиге')])
        self.assertEqual(result['missing_approved'],[])

    def test_hero_and_his_look_cannot_both_play_in_one_scene(self):
        self.setup_production()
        winter=self.new('look','Зима',self.char['id']);series=self.new('series','Пилот');scene=self.new('episode','Сцена',series['id'])
        self.assertEqual(self.save(scene,character_node_ids=[self.char['id'],winter['id']]).status_code,400)
        self.assertEqual(self.save(scene,character_node_ids=[winter['id']]).status_code,200)
        ids=[p['id'] for p in self.context(scene)['scene']['participants']]
        self.assertIn(winter['id'],ids);self.assertIn(self.char['id'],ids)


if __name__=='__main__':
    unittest.main()
