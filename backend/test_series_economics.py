import json
import unittest
from backend import main
from backend import test_production as production_tests


class SeriesCostTests(unittest.TestCase):
    setUp=production_tests.ProductionTests.setUp
    tearDown=production_tests.ProductionTests.tearDown
    setup_production=production_tests.ProductionTests.setup_production
    new=production_tests.ProductionTests.new

    def test_series_totals_unknown_costs_and_shared_budget(self):
        self.setup_production();series=self.new('series','Серия');scene=self.new('episode','Сцена',series['id'])
        projects=[]
        for name in ['Первый','Второй']:
            frame=self.new('frame',name,scene['id'])
            projects.append(self.client.post(f'/api/productions/{self.pid}/nodes/{frame["id"]}/open-project').json()['project_id'])
        path=f'/api/productions/{self.pid}/series/{series["id"]}'
        self.assertEqual(self.client.put(path+'/budget',json={'limit_usd':0.08}).status_code,200)
        with main.connect() as db:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',('series-job',projects[0],'image','piapi','task','completed',json.dumps({'payload':{'task_type':'test'}}),'{}',main.now()))
            db.execute('INSERT INTO generation_approvals VALUES(?,?,?,?,?)',('series-job',0.052,0.052,main.now(),'documentation_estimate'))
        report=self.client.get(path+'/economics').json()
        self.assertEqual(report['reserved_usd'],0.052)
        self.assertEqual(report['unknown_cost_count'],1)
        self.assertFalse(report['costs_complete'])
        with main.connect() as db:
            with self.assertRaises(main.HTTPException):main.security.check_budget(db,projects[1],0.052)
        self.assertEqual(self.client.put('/api/economics/jobs/series-job',json={'actual_usd':0.05,'note':'provider receipt'}).status_code,200)
        report=self.client.get(path+'/economics').json()
        self.assertTrue(report['costs_complete'])
        self.assertEqual(report['actual_usd_known'],0.05)
        self.assertEqual(self.client.put(path+'/budget',json={'limit_usd':None}).status_code,200)
        with main.connect() as db:main.security.check_budget(db,projects[1],0.052)
