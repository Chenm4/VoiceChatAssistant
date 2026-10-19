import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.api import routes
from backend.api.models import ChatMessage, ChatRequest, RegenerateMessageRequest, Session, SessionConfig


class StopParallelGenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_closes_every_model_stream_for_chat_and_regenerate(self):
        for regenerate in (False, True):
            with self.subTest(regenerate=regenerate):
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
                        streams.append(self)

                    def __aiter__(self):
                        return self

                    async def __anext__(self):
                        if self.first:
                            self.first = False
                            return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='partial'))])
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

                with patch.object(routes.session_storage, 'load_session', return_value=session), \
                     patch.object(routes.session_storage, 'save_session', return_value=True), \
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
                        if '"type": "content"' in part:
                            break
                    await asyncio.wait_for(iterator.aclose(), 1)
                self.assertEqual(len(streams), 2)
                self.assertTrue(all(stream.closed for stream in streams))
                self.assertTrue(all(client.closed for client in clients))
