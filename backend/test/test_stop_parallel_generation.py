from backend.test.workspace_case import WorkspaceAsyncTestCase, user_state
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.api import routes
from backend.api.models import ChatMessage, ChatRequest, RegenerateMessageRequest, Session, SessionConfig


class StopParallelGenerationTests(WorkspaceAsyncTestCase):
    async def test_disconnect_closes_every_model_stream_for_chat_and_regenerate(self):
        for regenerate, mode in ((r, m) for r in (False, True) for m in ("partial", "left_done", "complete")):
            with self.subTest(regenerate=regenerate, mode=mode):
                question = ChatMessage(id='question', role='user', content='question')
                session = Session(id='stop-test', title='test', created_at=1, updated_at=1,
                                  messages=[question], session_config=SessionConfig())
                source = SimpleNamespace(name='test', api_key='key', base_url='https://example.invalid')
                targets = [dict(key=f'test::{model}', model=model, source_name='test',
                                source=source, reasoning_effort='none') for model in ('a', 'b')]
                streams, clients = [], []

                class Stream:
                    def __init__(self):
                        self.closed = False
                        self.first = True
                        self.index = len(streams)
                        streams.append(self)

                    def __aiter__(self):
                        return self

                    async def __anext__(self):
                        if self.first:
                            self.first = False
                            return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='partial'))])
                        if mode == "complete" or (mode == "left_done" and self.index == 0):
                            raise StopAsyncIteration
                        await asyncio.Event().wait()

                    async def close(self):
                        self.closed = True

                class Client:
                    def __init__(self, **kwargs):
                        self.closed = False
                        clients.append(self)
                        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

                    async def create(self, **kwargs):
                        return Stream()

                    async def close(self):
                        self.closed = True

                with patch.object(user_state().session_storage, 'load_session', return_value=session), \
                     patch.object(user_state().session_storage, 'save_session', return_value=True), \
                     patch.object(routes, 'resolve_model_targets', return_value=targets), \
                     patch.object(routes, 'AsyncOpenAI', Client), \
                     patch.object(routes, 'log_model_request_context'), \
                     patch.object(routes, 'log_provider_request', return_value={}):
                    if regenerate:
                        response = await routes.regenerate_message(session.id, question.id,
                            RegenerateMessageRequest(message_id=question.id, new_content='edited'))
                    else:
                        response = await routes.chat(ChatRequest(message='new', session_id=session.id))
                    iterator = response.body_iterator
                    while True:
                        part = await asyncio.wait_for(iterator.__anext__(), 1)
                        event = __import__('json').loads(part.removeprefix('data: ').strip())
                        stop_event = {"partial": "content", "left_done": "model_done", "complete": "done"}[mode]
                        if event["type"] == stop_event:
                            if mode == "left_done":
                                answers_now = [item for item in session.messages if item.role == 'assistant']
                                self.assertEqual(answers_now[0].parallel_models[0]['content'], 'partial')
                            break
                    await asyncio.wait_for(iterator.aclose(), 1)
                answers = [item for item in session.messages if item.role == 'assistant']
                self.assertEqual(len(answers), 1)
                self.assertEqual([item['content'] for item in answers[0].parallel_models], ['partial', 'partial'])
                self.assertEqual(len(set(item.id for item in session.messages)), len(session.messages))
                self.assertEqual(len(streams), 2)
                self.assertTrue(all(stream.closed for stream in streams))
                self.assertTrue(all(client.closed for client in clients))
