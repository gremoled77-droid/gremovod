import io
import json
import unittest
from unittest.mock import AsyncMock,patch
from PIL import Image
from backend import main,test_production


class WorkspaceNavigationTests(unittest.TestCase):
    setUp=test_production.ProductionTests.setUp
    tearDown=test_production.ProductionTests.tearDown
    setup_production=test_production.ProductionTests.setup_production
    setup_frame=test_production.ProductionTests.setup_frame
    new=test_production.ProductionTests.new

    def test_workspace_hierarchy_and_saved_output_stay_with_original_frame(self):
        standalone=self.client.post('/api/projects',json={'title':'Other','state':{}}).json()['id']
        self.assertIsNone(self.client.get(f'/api/projects/{standalone}/workspace-location').json())
        self.setup_production();self.setup_frame()
        location=self.client.get(f'/api/projects/{self.frameproject}/workspace-location').json()
        self.assertEqual(location['production_id'],self.pid)
        self.assertEqual(location['frame']['id'],self.frame['id'])
        self.assertEqual(location['scene']['id'],self.frame['parent_id'])
        self.assertIsNotNone(location['series'])
        self.assertEqual(self.client.get('/api/projects/missing/workspace-location').status_code,404)
        stream=io.BytesIO();Image.new('RGB',(16,16),'blue').save(stream,format='PNG')
        # Simulate completion after the user has opened another project; no provider request.
        with main.connect() as db:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',('navigation-job',self.frameproject,'image','piapi','task','completed','{}',json.dumps({'data':{'output':{'image_url':'https://example.org/frame.png'}}}),main.now()))
        self.client.get('/api/projects/'+standalone)
        with patch.object(main,'download_image',AsyncMock(return_value=stream.getvalue())):
            saved=self.client.post('/api/jobs/navigation-job/outputs/0/save')
        self.assertEqual(saved.status_code,200,saved.text)
        details=self.client.get(self.framebase).json()
        self.assertEqual(len(details['files']),1)
        self.assertEqual(details['files'][0]['asset_id'],saved.json()['id'])
        self.assertFalse(self.client.get('/api/library',params={'project_id':standalone}).json())
        original=self.client.get('/api/activity',params={'project_id':self.frameproject}).json()['items']
        other=self.client.get('/api/activity',params={'project_id':standalone}).json()['items']
        self.assertEqual(original[0]['asset_ids'],[saved.json()['id']]);self.assertFalse(other)
