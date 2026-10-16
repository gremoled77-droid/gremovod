import unittest
from backend import test_production,visual_plan


class VisualPlanTests(unittest.TestCase):
    setUp=test_production.ProductionTests.setUp
    tearDown=test_production.ProductionTests.tearDown
    setup_production=test_production.ProductionTests.setup_production
    new=test_production.ProductionTests.new

    def tree(self):
        self.setup_production()
        series=self.new('series','Серия');scene=self.new('episode','Встреча',series['id']);frame=self.new('frame','Крупный план',scene['id'])
        return series,scene,frame

    def test_save_read_and_isolation_from_entity_revision(self):
        series,scene,frame=self.tree()
        before=self.client.get(f'/api/productions/{self.pid}/nodes/{frame["id"]}/editor').json()['revision']
        url=lambda n:f'/api/productions/{self.pid}/nodes/{n["id"]}/visual-plan'
        r=self.client.put(url(frame),json={'space':'flat','line':'diagonal','tone':'conceal','sector_start':3,'sector_end':6,'story':7,'visual':8,'beat':2,'note':'тень на пассажире','beats':'игнорируется'})
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['beats'],'')
        self.assertEqual(self.client.put(url(scene),json={'beats':'1 Знакомство\n2 Спор','story':4}).status_code,200)
        got=self.client.get(f'/api/productions/{self.pid}/series/{series["id"]}/visual-plan').json()['plans']
        self.assertEqual(got[frame['id']]['space'],'flat');self.assertEqual(got[frame['id']]['sector_end'],6)
        self.assertIn('Спор',got[scene['id']]['beats'])
        self.assertEqual(self.client.get(f'/api/productions/{self.pid}/nodes/{frame["id"]}/editor').json()['revision'],before)

    def test_rejects_bad_values_wrong_kind_and_foreign_ids(self):
        series,scene,frame=self.tree()
        url=lambda n:f'/api/productions/{self.pid}/nodes/{n}/visual-plan'
        self.assertEqual(self.client.put(url(frame['id']),json={'space':'huge'}).status_code,422)
        self.assertEqual(self.client.put(url(frame['id']),json={'story':11}).status_code,422)
        self.assertEqual(self.client.put(url(frame['id']),json={'sector_start':0}).status_code,422)
        self.assertEqual(self.client.put(url(series['id']),json={}).status_code,400)
        self.assertEqual(self.client.put(url('absent'),json={}).status_code,404)
        self.assertEqual(self.client.get(f'/api/productions/{self.pid}/series/{scene["id"]}/visual-plan').status_code,404)

    def test_damaged_stored_value_falls_back(self):
        self.assertEqual(visual_plan.clean({'space':'bogus','story':3})['space'],'')
        self.assertEqual(visual_plan.clean('x')['story'],None)


class VisualRulesTests(unittest.TestCase):
    setUp=test_production.ProductionTests.setUp
    tearDown=test_production.ProductionTests.tearDown
    setup_production=test_production.ProductionTests.setup_production
    new=test_production.ProductionTests.new
    tree=VisualPlanTests.tree

    def test_rules_save_and_compile_for_frame_with_inheritance(self):
        series,scene,frame=self.tree()
        loc=self.new('location','Салон');hero=self.new('character','Пассажир')
        url=lambda n:f'/api/productions/{self.pid}/nodes/{n["id"]}/visual-rules'
        self.assertEqual(self.client.put(url(series),json={'space':'flat','palette':'ochre, faded teal','camera':'locked in the car'}).status_code,200)
        self.assertEqual(self.client.put(url(loc),json={'line':'vertical','tone':'conceal'}).status_code,200)
        self.assertEqual(self.client.put(url(hero),json={'shape':'triangle'}).status_code,200)
        editor=f'/api/productions/{self.pid}/nodes/{scene["id"]}/editor'
        saved=self.client.put(editor,json={'base_revision':self.client.get(editor).json()['revision'],'notes':'сцена','character_node_ids':[hero['id']],'location_node_id':loc['id']})
        self.assertEqual(saved.status_code,200,saved.text)
        self.client.put(f'/api/productions/{self.pid}/nodes/{frame["id"]}/visual-plan',json={'space':'deep','note':'mirror reflection'})
        text=self.client.get(url(frame)).json()
        self.assertFalse(text['editable'])
        for part in ('flat frontal','ochre, faded teal','vertical lines','shadow partly conceals','triangular','deep space','mirror reflection'):
            self.assertIn(part,text['prompt'])
        self.assertLess(text['prompt'].index('Series'),text['prompt'].index('Shot plan'))

    def test_rules_validation_and_empty(self):
        series,scene,frame=self.tree()
        url=lambda n:f'/api/productions/{self.pid}/nodes/{n}/visual-rules'
        self.assertEqual(self.client.get(url(frame['id'])).json()['prompt'],'')
        self.assertEqual(self.client.put(url(frame['id']),json={}).status_code,400)
        self.assertEqual(self.client.put(url(series['id']),json={'palette':'x'*301}).status_code,422)
        self.assertEqual(self.client.put(url('absent'),json={}).status_code,404)


if __name__=='__main__':unittest.main()
