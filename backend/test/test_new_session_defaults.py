from backend.test.workspace_case import WorkspaceTestCase, user_state
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.api import routes
from backend.services.session_storage import SessionStorage

class NewSessionDefaultsTests(WorkspaceTestCase):
    def test_new_session_api_persists_both_models_and_reasoning_efforts(self):
        app = FastAPI()
        app.include_router(routes.router, prefix='/api')
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(user_state(), 'current_session_id', None), \
             patch.object(user_state(), 'current_session_cache', None):
            storage = SessionStorage(directory)
            with patch.object(user_state(), 'session_storage', storage), TestClient(app) as client:
                response = client.post('/api/sessions', params={'title':'default-test'})
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload['success'])
                saved = storage.load_session(payload['session']['id'])
                self.assertEqual(saved.session_config.models, ['qwen3.8-max','qwen3.7-plus'])
                self.assertEqual([(target.source_name,target.model,target.reasoning_effort)
                                  for target in saved.session_config.model_targets],
                                 [('通义千问','qwen3.8-max','none'),('通义千问','qwen3.7-plus','low')])

    def test_models_remain_available_without_private_prompt(self):
        from backend.services.session_prompt import create_default_session_config
        with patch('backend.services.session_prompt.load_prompt_template_snapshot', side_effect=ValueError('missing')):
            config = create_default_session_config()
        self.assertEqual(config.models, ['qwen3.8-max', 'qwen3.7-plus'])
        self.assertEqual(len(config.model_targets), 2)
        self.assertEqual(config.system_prompt, '')
        self.assertEqual(config.background_mode, 'none')
