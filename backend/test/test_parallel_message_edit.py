from backend.test.workspace_case import WorkspaceAsyncTestCase, user_state
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from backend.api import routes
from backend.api.models import ChatMessage, Session, MessageUpdateRequest

class ParallelMessageEditTests(WorkspaceAsyncTestCase):
    def make_session(self):
        return Session(id='edit-test', title='test', created_at=1, updated_at=1, messages=[
            ChatMessage(id='answer', role='assistant', content='container', parallel_models=[
                {'model_key': 'left', 'content': 'A'},
                {'model_info': {'provider': 'source', 'name': 'model'}, 'content': 'B'}
            ])])

    async def test_only_selected_model_changes(self):
        session = self.make_session()
        with patch.object(user_state().session_storage, 'load_session', return_value=session), \
             patch.object(user_state().session_storage, 'save_session', return_value=True) as save:
            await routes.update_message('edit-test', 'answer', MessageUpdateRequest(content='changed', model_key='source::model'))
            self.assertEqual([entry['content'] for entry in session.messages[0].parallel_models], ['A', 'changed'])
            self.assertEqual(session.messages[0].content, 'container')
            save.assert_called_once_with(session)

    async def test_unknown_model_is_not_saved(self):
        session = self.make_session()
        with patch.object(user_state().session_storage, 'load_session', return_value=session), \
             patch.object(user_state().session_storage, 'save_session') as save:
            with self.assertRaises(HTTPException) as error:
                await routes.update_message('edit-test', 'answer', MessageUpdateRequest(content='changed', model_key='unknown'))
            self.assertEqual(error.exception.status_code, 404)
            self.assertEqual([entry['content'] for entry in session.messages[0].parallel_models], ['A', 'B'])
            save.assert_not_called()
