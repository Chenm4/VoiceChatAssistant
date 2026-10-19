from backend.test.workspace_case import WorkspaceTestCase, user_state
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import routes
from backend.api.models import Session, SessionConfig
from backend.services.session_storage import SessionStorage


class RightClickSettingsTests(WorkspaceTestCase):
    def test_save_and_reload_both_actions_through_api_and_disk(self):
        app = FastAPI()
        app.include_router(routes.router, prefix='/api')
        with tempfile.TemporaryDirectory() as directory:
            storage = SessionStorage(directory)
            now = int(time.time())
            session = Session(id='right-click-test', title='test', created_at=now,
                              updated_at=now, session_config=SessionConfig())
            self.assertTrue(storage.save_session(session))
            with patch.object(user_state(), 'session_storage', storage), \
                 patch.object(user_state(), 'current_session_id', None):
                with TestClient(app) as client:
                    for action in ('photo', 'record'):
                        saved = client.put(f'/api/sessions/{session.id}/config',
                                           json={'right_click_action': action})
                        self.assertEqual(saved.status_code, 200)
                        self.assertEqual(saved.json()['config']['right_click_action'], action)
                        loaded = client.get(f'/api/sessions/{session.id}/config')
                        self.assertEqual(loaded.status_code, 200)
                        self.assertEqual(storage.load_session(session.id).session_config.right_click_action, action)
                        self.assertEqual(loaded.json()['config']['right_click_action'], action)

    def test_existing_sessions_default_to_record(self):
        self.assertEqual(SessionConfig.model_validate({}).right_click_action, 'record')


if __name__ == '__main__':
    unittest.main()
