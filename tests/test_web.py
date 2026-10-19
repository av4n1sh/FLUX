import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from flux.storage import Store
from flux.web import create_app


class WebTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = Store(Path(self.folder.name) / 'web.db')
        self.client = TestClient(create_app(self.store, lambda messages: 'Hello from Flux', token='x'*32))
        self.headers = {'Authorization': 'Bearer ' + 'x'*32}

    def action(self, **data):
        response = self.client.post('/api/action', json=data, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        return response.json()['events']

    def test_auth_and_validation(self):
        self.assertEqual(self.client.post('/api/action', json={'action':'ready'}).status_code,401)
        self.assertEqual(self.client.post('/api/action', json=[], headers=self.headers).status_code,400)
        self.assertEqual(self.client.post('/api/action', content='x'*150001, headers=self.headers).status_code,413)
        with self.assertRaises(RuntimeError):
            create_app(self.store, token='short')

    def test_chat_memory_and_confirmed_deletion(self):
        events = self.action(action='send', text='My favorite color is blue.')
        snapshot = next(e for e in events if e['type']=='snapshot')
        self.assertEqual(len(snapshot['messages']),2)
        session = snapshot['session']
        self.action(action='saveMemory',text='I enjoy hiking.',category='Other')
        self.assertTrue(self.store.memories())
        self.action(action='confirmDelete',token='wrong')
        self.assertEqual(len(self.store.sessions()),1)
        confirmation = self.action(action='requestDelete',kind='conversation',id=session)[0]
        self.action(action='confirmDelete',token=confirmation['token'])
        self.assertEqual(self.store.sessions(),[])
        self.assertTrue(self.store.memories())

    def test_failed_model_preserves_history(self):
        def fail(messages):
            raise RuntimeError('Model unavailable')
        client = TestClient(create_app(self.store, fail, token='x'*32))
        events = client.post('/api/action',json={'action':'send','text':'hello'},headers=self.headers).json()['events']
        self.assertTrue(any(e['type']=='sendRejected' for e in events))
        self.assertFalse(self.store.messages(self.store.sessions()[0][0]))

    def test_cors_restricts_origin(self):
        for origin, allowed in [('http://localhost:8080',True),('https://untrusted.example',False)]:
            response = self.client.options('/api/action',headers={'Origin':origin,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type'})
            self.assertEqual('access-control-allow-origin' in response.headers,allowed)


if __name__ == '__main__':
    unittest.main()
