import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException
from backend.test.workspace_case import WorkspaceAsyncTestCase
from backend.api.models import Session, ChatMessage, ConfigSource, ModelTarget
from backend.services.request_snapshots import save_request_snapshot, load_snapshot, messages_digest
from backend.services.user_workspace import user_state
from backend.api.model_comparison import create_comparison, list_comparisons, CompareRequest


class ComparisonTests(WorkspaceAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.session = Session(id='session_test', title='test', created_at=1700000000, updated_at=1700000000, messages=[ChatMessage(id='question', role='user', content='original')])
        user_state().session_storage.save_session(self.session)
        self.source = ConfigSource(name='通义千问', api_key='test-key', base_url='https://example.test', models=['qwen3.8-max', 'qwen3.7-plus'])
        self.params = {'model':'qwen3.8-max', 'messages':[
            {'role':'system', 'content':'original prompt'},
            {'role':'user', 'content':'original history'},
            {'role':'user', 'content':[{'type':'text','text':'original'}, {'type':'image_url','image_url':{'url':'data:image/png;base64,aGVsbG8='}}]}],
            'temperature':0.4, 'top_p':0.8, 'stream':True, 'extra_body':{'enable_thinking':False}}

    async def test_exact_replay_after_history_prompt_and_image_changes(self):
        original = copy.deepcopy(self.params)
        snap = save_request_snapshot(self.session.id, 'question', self.source, self.params)
        self.params['messages'][0]['content'] = 'changed'
        self.session.messages[0].content = 'edited question'
        self.session.messages.append(ChatMessage(id='later', role='user', content='future history'))
        user_state().session_storage.save_session(self.session)
        self.test_workspace.settings['DEFAULT_SESSION_CONFIG'] = {'system_prompt':'new prompt'}
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='better answer', reasoning_content='reason'))], usage=None)
        client = AsyncMock()
        client.chat.completions.create.return_value = response
        client.__aenter__.return_value = client
        with patch('backend.api.model_comparison.AsyncOpenAI', return_value=client):
            result = await create_comparison(self.session.id, 'question', CompareRequest(snapshot_id=snap['id'], target=ModelTarget(source_name='通义千问',model='qwen3.7-plus')))
            await asyncio.gather(*list(self.test_workspace.tasks.values()))
        sent = client.chat.completions.create.call_args.kwargs
        self.assertEqual(sent['messages'], original['messages'])
        self.assertEqual(sent['temperature'], 0.4)
        self.assertEqual(sent['model'], 'qwen3.7-plus')
        saved = await list_comparisons(self.session.id, 'question')
        self.assertEqual(saved['results'][0]['content'], 'better answer')
        self.assertEqual(saved['results'][0]['messages_sha256'], messages_digest(original['messages']))
        self.assertEqual(len(user_state().session_storage.load_session(self.session.id).messages), 2)
        self.assertNotIn('test-key', json.dumps(saved))
        self.assertEqual(load_snapshot(self.session.id, 'question', snap['id'])['parameters'], original)

    async def test_old_message_rejected_and_missing_session_isolated(self):
        with self.assertRaises(HTTPException) as error:
            await create_comparison(self.session.id, 'question', CompareRequest(snapshot_id='missing', target=ModelTarget(source_name='通义千问',model='qwen3.7-plus')))
        self.assertEqual(error.exception.status_code, 404)
        with self.assertRaises(HTTPException):
            await list_comparisons('other_user_session', 'question')
        self.assertEqual((await list_comparisons(self.session.id, 'question'))['snapshots'], [])

    async def test_failed_comparison_is_saved_without_provider_error_body(self):
        snap = save_request_snapshot(self.session.id, 'question', self.source, self.params)
        client = AsyncMock(); client.__aenter__.return_value = client
        client.chat.completions.create.side_effect = RuntimeError('secret-provider-token')
        with patch('backend.api.model_comparison.AsyncOpenAI', return_value=client):
            await create_comparison(self.session.id, 'question', CompareRequest(snapshot_id=snap['id'], target=ModelTarget(source_name='通义千问',model='qwen3.7-plus')))
            await asyncio.gather(*list(self.test_workspace.tasks.values()))
        saved = await list_comparisons(self.session.id, 'question')
        self.assertEqual(saved['results'][0]['status'], 'error')
        self.assertNotIn('secret-provider-token', json.dumps(saved))

    async def test_legacy_rebuild_excludes_all_later_turns_and_restores_scene(self):
        from backend.api.models import SessionConfig, PromptScene
        from backend.services.legacy_comparison import reconstruct_request
        from backend.services.user_workspace import write_json
        self.session.session_config = SessionConfig(system_prompt='saved system',
            active_scene=PromptScene(id='later_scene', name='later scene', rules='DO_NOT_INCLUDE_LATER_SCENE'))
        self.session.messages = [
            ChatMessage(id='prior', role='user', content='earlier question', created_at=100),
            ChatMessage(id='question', role='user', content='selected question', created_at=100),
            ChatMessage(id='answer', parent_id='question', role='assistant', content='old answer', scene_name='old scene', created_at=100),
            ChatMessage(id='future', role='user', content='DO_NOT_INCLUDE_FUTURE', created_at=100),
            ChatMessage(id='future_answer', parent_id='future', role='assistant', content='DO_NOT_INCLUDE_FUTURE_ANSWER', created_at=100)]
        user_state().session_storage.save_session(self.session)
        write_json(self.test_workspace.path('prompt_scenes.json'), {'scenes':[
            {'id':'old', 'name':'old scene', 'rules':'saved old scene rules'}]})
        record = reconstruct_request(self.session.id, 'answer')
        text = json.dumps(record['parameters']['messages'])
        self.assertIn('earlier question', text)
        self.assertIn('selected question', text)
        self.assertIn('saved old scene rules', text)
        self.assertIn('saved system', text)
        self.assertNotIn('DO_NOT_INCLUDE', text)
        self.assertNotIn('old answer', text)
        self.assertEqual(record['reconstruction']['mode'], 'approximate')
        self.assertEqual(record['reconstruction']['history_candidate_ids'], ['prior'])
        self.assertEqual(user_state().session_storage.load_session(self.session.id).session_config.active_scene.name, 'later scene')
        self.session.messages[0].content = 'changed later'
        user_state().session_storage.save_session(self.session)
        self.assertEqual(load_snapshot(self.session.id, 'question', record['id'])['parameters']['messages'], record['parameters']['messages'])
