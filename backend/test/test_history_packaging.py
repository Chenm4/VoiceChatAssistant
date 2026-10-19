from backend.test.workspace_case import WorkspaceTestCase
import unittest
from backend.api.models import ChatMessage, Session
from backend.api.routes import build_message_path
from backend.services.chat_context import build_scoped_request

class HistoryPackagingTests(WorkspaceTestCase):
    def test_every_historical_question_is_a_separate_user_message(self):
        history = [{'role':'user','content':f'问题 {i}'} for i in range(12)]
        request = build_scoped_request(history, '当前问题')
        self.assertEqual(len(request), 14)
        self.assertEqual([message['role'] for message in request], ['system'] + ['user'] * 13)
        self.assertEqual([message['content'].split('\n', 1)[1] for message in request[1:-1]], [f'问题 {i}' for i in range(12)])
        self.assertTrue(request[-1]['content'].endswith('【当前问题：唯一待回答内容】\n当前问题'))
        self.assertLess(request[-1]['content'].index('本次请求只回答'), request[-1]['content'].index('【当前问题：唯一待回答内容】'))
        self.assertIn('最后一条 user', request[0]['content'])

    def test_assistant_history_is_excluded_even_when_old_config_enables_it(self):
        from backend.api.models import SessionConfig
        from backend.api.routes import resolve_chat_context_config
        history = [{'role':'system','content':'规则'}, {'role':'user','content':'旧问题'},
                   {'role':'assistant','content':'很长的旧答案' * 1000}]
        for enabled in (False, True):
            request = build_scoped_request(history, '新问题', include_assistant=enabled)
            self.assertEqual([message['role'] for message in request], ['system','user','user'])
            self.assertNotIn('很长的旧答案', str(request))
        self.assertFalse(resolve_chat_context_config(SessionConfig(include_assistant_history=True))['include_assistant_history'])

    def test_regenerate_flat_session_keeps_all_middle_turns_but_excludes_future(self):
        session = Session(id='flat',title='test',created_at=1,updated_at=1,messages=[
            ChatMessage(id='first',role='user',content='first'),
            ChatMessage(id='answer',role='assistant',content='reply',parent_id='first'),
            ChatMessage(id='middle',role='user',content='middle'),
            ChatMessage(id='target',role='user',content='target'),
            ChatMessage(id='future',role='user',content='future')])
        self.assertEqual([m.id for m in build_message_path(session,'target')],['first','answer','middle','target'])

    def test_branched_history_follows_parents_and_excludes_other_branches(self):
        session = Session(id='tree',title='test',created_at=1,updated_at=1,messages=[
            ChatMessage(id='first',role='user',content='first'),
            ChatMessage(id='answer',role='assistant',content='reply',parent_id='first'),
            ChatMessage(id='other',role='user',content='other',parent_id='answer'),
            ChatMessage(id='target',role='user',content='target',parent_id='answer')])
        self.assertEqual([m.id for m in build_message_path(session,'target')],['first','answer','target'])
