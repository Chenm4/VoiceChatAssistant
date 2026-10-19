import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.api.models import ChatMessage, MessageAttachment, PromptScene, SceneCatalog, Session, SessionConfig, RegenerateMessageRequest
from backend.services import prompt_scenes
from backend.services.session_prompt import compose_session_system_prompt, render_session_user_prompt


class PromptSceneTests(unittest.TestCase):
    def test_exam_buttons_have_independent_rules_and_restore_default(self):
        scenes = prompt_scenes.exam_scenes()
        self.assertEqual([scene.name for scene in scenes], ['笔试专用', 'AI Coding 提问助手'])
        self.assertIn('algorithm_answer', scenes[0].rules)
        config = SessionConfig(system_prompt='INTERVIEW', active_scene=scenes[0], background_mode='none')
        session = Session(id='exam', title='test', created_at=1, updated_at=1, session_config=config)
        self.assertIn(scenes[0].rules, compose_session_system_prompt(session))
        self.assertNotIn('COMMON', compose_session_system_prompt(session))
        config.active_scene = None
        self.assertEqual(compose_session_system_prompt(session), 'INTERVIEW')

    def test_active_scene_excludes_original_background_and_template(self):
        config = SessionConfig(system_prompt='COMMON', background_mode='shared',
                               user_prompt_template='OLD {{question}}',
                               active_scene=PromptScene(id='a', name='A', rules='A RULES', background='A FACTS'),
                               scene_common_rules='STALE RULES')
        session = Session(id='s', title='test', created_at=1, updated_at=1, session_config=config)
        with patch('backend.services.session_prompt.load_shared_background', return_value='B FACTS') as shared:
            prompt = compose_session_system_prompt(session)
            shared.assert_not_called()
        self.assertTrue(prompt.startswith('COMMON\n\n【当前场景】'))
        self.assertIn('COMMON', prompt)
        self.assertNotIn('STALE RULES', prompt)
        self.assertNotIn('B FACTS', prompt)
        user_prompt = render_session_user_prompt(session, 'question')
        self.assertIn('A RULES', prompt)
        self.assertIn('A FACTS', prompt)
        self.assertEqual(user_prompt, 'question')
        self.assertNotIn('OLD', user_prompt)
        config.active_scene = None
        with patch('backend.services.session_prompt.load_shared_background', return_value='B FACTS'):
            self.assertIn('B FACTS', compose_session_system_prompt(session))
        self.assertEqual(render_session_user_prompt(session, 'question'), 'OLD question')

    def test_catalog_round_trip_and_session_snapshot(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(prompt_scenes, 'CATALOG_PATH', Path(directory) / 'scenes.json'):
            self.assertTrue(prompt_scenes.load_catalog().scenes)
            catalog = SceneCatalog(scenes=[PromptScene(id='project', name='项目', background='资料')])
            prompt_scenes.save_catalog(catalog)
            self.assertEqual(prompt_scenes.load_catalog(), catalog)
            config = SessionConfig(active_scene=catalog.scenes[0], scene_common_rules=catalog.common_rules)
            restored = SessionConfig(**json.loads(config.model_dump_json()))
            self.assertEqual(restored.active_scene.background, '资料')

    def test_scene_rerun_preserves_history_images_and_old_answer(self):
        from backend.api import routes
        image = MessageAttachment(id='image', mime_type='image/webp', filename='image.webp')
        previous = ChatMessage(id='previous', role='user', content='Earlier context', children_ids=['q'])
        question = ChatMessage(id='q', role='user', parent_id='previous', content='Question', attachments=[image], children_ids=['a'])
        answer = ChatMessage(id='a', role='assistant', parent_id='q', content='Old answer', scene_name='Old project')
        session = Session(id='scene_test', title='test', created_at=1, updated_at=1, messages=[previous, question, answer],
                          session_config=SessionConfig(active_scene=PromptScene(id='new', name='New project', background='New facts')))
        source = SimpleNamespace(name='test', api_key='test-key', base_url='https://example.invalid')
        target = {'key': 'test::model', 'model': 'model', 'source_name': 'test', 'source': source, 'reasoning_effort': 'none'}
        completion = Mock()
        completion.chat.completions.create.return_value = iter([SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='New answer'))])])

        async def run():
            response = await routes.regenerate_message(session.id, 'q', RegenerateMessageRequest(message_id='q', new_content='Question', preserve_answer=True))
            return [part async for part in response.body_iterator]

        with patch.object(routes.session_storage, 'load_session', return_value=session), \
             patch.object(routes.session_storage, 'save_session', return_value=True), \
             patch.object(routes, 'resolve_model_targets', return_value=[target]), \
             patch.object(routes, 'OpenAI', return_value=completion), \
             patch.object(routes, '_multimodal_user_content', side_effect=lambda sid, content, images: content) as multimodal, \
             patch.object(routes, 'log_model_request_context'), \
             patch.object(routes, 'log_provider_request', return_value={}), \
             patch.object(routes, 'log_model_interaction'):
            chunks = asyncio.run(run())
        self.assertTrue(any('"type": "done"' in part for part in chunks), chunks)
        self.assertEqual(question.answer_versions[0]['content'], 'Old answer')
        self.assertEqual(question.attachments[0].id, 'image')
        self.assertEqual(multimodal.call_args.args[2][0].id, 'image')
        self.assertEqual(sum(msg.role == 'user' for msg in session.messages), 2)
        self.assertEqual(session.messages[-1].scene_name, 'New project')
        sent = str(completion.chat.completions.create.call_args.kwargs['messages'])
        self.assertIn('Earlier context', sent)
        self.assertIn('New facts', sent)
        self.assertNotIn('Old answer', sent)
        self.assertEqual(question.content, 'Question')
        messages = completion.chat.completions.create.call_args.kwargs['messages']
        self.assertEqual(sent.count('New facts'), 1)
        self.assertIn('New facts', messages[0]['content'])
        self.assertNotIn('New facts', messages[-1]['content'])

    def test_session_settings_edits_update_scene_catalog_and_effective_prompt(self):
        from backend.api import routes
        scene = PromptScene(id='project', name='Project', rules='old', background='old facts')
        session = Session(id='sync', title='test', created_at=1, updated_at=1,
                          session_config=SessionConfig(system_prompt='common', active_scene=scene))
        config = session.session_config.model_copy(deep=True)
        config.system_prompt = 'new common'
        config.active_scene.rules = 'new scene rules'
        config.active_scene.background = 'new project facts'
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(prompt_scenes, 'CATALOG_PATH', Path(directory) / 'scenes.json'), \
             patch.object(routes.session_storage, 'load_session', return_value=session), \
             patch.object(routes.session_storage, 'save_session', return_value=True):
            prompt_scenes.save_catalog(SceneCatalog(scenes=[scene]))
            asyncio.run(routes.update_session_config(session.id, config))
            stored = prompt_scenes.load_catalog().scenes[0]
        self.assertEqual(stored.rules, 'new scene rules')
        self.assertEqual(stored.background, 'new project facts')
        effective = compose_session_system_prompt(session)
        self.assertIn('new common', effective)
        self.assertTrue(effective.startswith('new common\n\n【当前场景】'))
        user_prompt = render_session_user_prompt(session, 'question')
        self.assertIn('new scene rules', effective)
        self.assertIn('new project facts', effective)
        config.active_scene = None
        self.assertEqual(compose_session_system_prompt(session), 'new common')

    def test_outdated_rerun_cannot_overwrite_new_scene_config(self):
        from backend.api import routes
        question = ChatMessage(id='q', role='user', content='Question', children_ids=[])
        session = Session(id='latest-wins', title='test', created_at=1, updated_at=1,
                          messages=[question], session_config=SessionConfig())
        source = SimpleNamespace(name='test', api_key='test-key', base_url='https://example.invalid')
        target = {'key': 'test::model', 'model': 'model', 'source_name': 'test', 'source': source, 'reasoning_effort': 'none'}
        completion = Mock()
        completion.chat.completions.create.return_value = iter([SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='stale answer'))])])
        async def run():
            response = await routes.regenerate_message(session.id, 'q', RegenerateMessageRequest(message_id='q', new_content='Question'))
            async for part in response.body_iterator:
                if 'stale answer' in part:
                    # A new scene supersedes this request while its stream is alive.
                    routes.generation_epochs[session.id] = 'new-scene'
        with patch.object(routes.session_storage, 'load_session', return_value=session), \
             patch.object(routes.session_storage, 'save_session', return_value=True) as save, \
             patch.object(routes, 'resolve_model_targets', return_value=[target]), \
             patch.object(routes, 'OpenAI', return_value=completion), \
             patch.object(routes, 'log_model_request_context'), \
             patch.object(routes, 'log_provider_request', return_value={}), \
             patch.object(routes, 'log_model_interaction'):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(run())
            self.assertEqual(save.call_count, 1)  # Initial question only, never the stale answer.

    def test_long_scene_is_attached_once_across_rounds_switches_and_history_modes(self):
        from backend.services.chat_context import build_scoped_request
        for include_assistant in (False, True):
            with self.subTest(include_assistant=include_assistant):
                rules = '场景长提示' * 6000
                session = Session(id='long', title='test', created_at=1, updated_at=1,
                                  session_config=SessionConfig(system_prompt='COMMON',
                                      active_scene=PromptScene(id='a', name='A', rules=rules)))
                history = []
                for turn in range(3):
                    question = f'原始问题 {turn}'
                    request = build_scoped_request(
                        [{'role': 'system', 'content': compose_session_system_prompt(session)}] + history,
                        render_session_user_prompt(session, question), include_assistant=include_assistant)
                    self.assertEqual(str(request).count(rules), 1)
                    self.assertIn(rules, request[0]['content'])
                    self.assertNotIn(rules, request[-1]['content'])
                    history.extend([{'role': 'user', 'content': question},
                                    {'role': 'assistant', 'content': f'回答 {turn}'}])
                session.session_config.active_scene = PromptScene(id='b', name='B', rules='新的场景要求')
                request = build_scoped_request([{'role': 'system', 'content': compose_session_system_prompt(session)}] + history, render_session_user_prompt(session, '原始问题 2'),
                                               include_assistant=include_assistant)
                self.assertNotIn(rules, str(request))
                self.assertEqual(str(request).count('新的场景要求'), 1)
                self.assertNotIn('新的场景要求', str(history))
                session.session_config.active_scene = None
                self.assertEqual(render_session_user_prompt(session, '原始问题'), '原始问题')
