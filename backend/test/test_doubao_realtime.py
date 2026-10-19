import asyncio
import base64
import json
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.services import doubao_realtime as protocol
from backend.api.doubao_realtime import router, StartOptions, session_instructions


class FakeUpstream:
    def __init__(self):
        self.sent = []
    async def __aenter__(self):
        self.frames = asyncio.Queue()
        return self
    async def __aexit__(self, *args):
        pass
    async def send(self, raw):
        event = json.loads(raw)
        self.sent.append(event)
        if event['type'] == 'session.create':
            self.frames.put_nowait(json.dumps({'type': 'session.created'}))
        if event['type'] == 'input_audio_buffer.commit':
            for item in [
                {'type': 'response.output_audio.delta', 'delta': 'AAE='},
                {'type': 'response.output_text.delta', 'delta': '完整回复'},
                {'type': 'response.output_text.done', 'text': '完整回复'},
            ]:
                self.frames.put_nowait(json.dumps(item))
        if event['type'] == 'session.close':
            self.frames.put_nowait(json.dumps({'type': 'session.closed'}))
    async def recv(self):
        return await self.frames.get()
    def __aiter__(self):
        return self
    async def __anext__(self):
        return await self.recv()


class ManualRecordingTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix='/api')
        self.client = TestClient(app)

    def test_completed_recording_sends_text_only_and_closes(self):
        fake = FakeUpstream()
        with patch('backend.api.doubao_realtime.websockets.connect', return_value=fake), \
             patch.object(protocol, 'credentials', return_value=('app', 'token')), \
             patch('backend.api.doubao_realtime.load_recording', return_value=b'\0\0' * 320), \
             patch('backend.api.doubao_realtime.session_instructions', return_value='复用提示词'):
            with self.client.websocket_connect('/api/doubao-realtime/ws') as ws:
                self.assertEqual(fake.sent, [])  # Nothing reaches provider before submit.
                ws.send_json({'type': 'start', 'session_id': 's', 'audio_file': 'recording.wav', 'text': '完整问题'})
                self.assertEqual(ws.receive_json()['type'], 'ready')
                self.assertEqual(ws.receive_json()['data']['content'], '完整回复')
                self.assertEqual(ws.receive_json()['event'], 559)
                self.assertEqual(ws.receive_json()['type'], 'complete')
                self.assertEqual(ws.receive()['type'], 'websocket.close')
        kinds = [event['type'] for event in fake.sent]
        self.assertEqual(kinds, ['session.create', 'input_audio_buffer.append', 'input_audio_buffer.commit', 'input_audio_mute.commit', 'session.close'])
        self.assertIn('完整问题', fake.sent[0]['session']['instructions'])
        self.assertIn('复用提示词', fake.sent[0]['session']['instructions'])

    def test_typed_question_uses_local_audio_adapter_without_loading_a_recording(self):
        from unittest.mock import AsyncMock
        fake = FakeUpstream()
        with patch('backend.api.doubao_realtime.websockets.connect', return_value=fake), \
             patch.object(protocol, 'credentials', return_value=('app', 'token')), \
             patch('backend.api.doubao_realtime.text_input_pcm', new_callable=AsyncMock, return_value=b'\0\0' * 320) as synthesize, \
             patch('backend.api.doubao_realtime.load_recording') as recording, \
             patch('backend.api.doubao_realtime.session_instructions', return_value='复用提示词'):
            with self.client.websocket_connect('/api/doubao-realtime/ws') as ws:
                ws.send_json({'type': 'start', 'session_id': 's', 'text': 'Pytest 是用来做什么的？'})
                self.assertEqual(ws.receive_json()['type'], 'ready')
                self.assertEqual(ws.receive_json()['data']['content'], '完整回复')
                self.assertEqual(ws.receive_json()['event'], 559)
                self.assertEqual(ws.receive_json()['type'], 'complete')
        synthesize.assert_awaited_once_with('Pytest 是用来做什么的？')
        recording.assert_not_called()

    def test_old_live_start_is_rejected_before_provider_connection(self):
        with patch('backend.api.doubao_realtime.websockets.connect') as connect:
            with self.client.websocket_connect('/api/doubao-realtime/ws') as ws:
                ws.send_json({'type': 'start'})
                self.assertEqual(ws.receive_json()['type'], 'error')
            connect.assert_not_called()

    def test_unowned_recording_is_rejected(self):
        from types import SimpleNamespace
        from backend.api.doubao_realtime import load_recording
        with patch('backend.api.doubao_realtime.session_storage.load_session', return_value=SimpleNamespace(audio_files=[])):
            with self.assertRaises(ValueError):
                load_recording(StartOptions(type='start', session_id='s', audio_file='other.wav', text='问题'))

    def test_audio_events_are_never_forwarded(self):
        for kind in ['started', 'delta', 'done']:
            self.assertIsNone(protocol.normalize_event({'type': 'response.output_audio.' + kind, 'delta': 'invalid base64'}))

    def test_config_has_no_audio_output_or_credentials(self):
        with patch.object(protocol, 'credentials', return_value=('app', 'private-token')):
            response = self.client.get('/api/doubao-realtime/config')
        self.assertNotIn('private-token', response.text)
        self.assertNotIn('output_audio', response.json())

    def test_shared_prompt_composition(self):
        with patch('backend.api.doubao_realtime.session_storage.load_session', return_value=object()), \
             patch('backend.api.doubao_realtime.compose_session_system_prompt', return_value='共享背景'), \
             patch('backend.api.doubao_realtime.render_session_user_prompt', return_value='场景规则'):
            self.assertEqual(session_instructions('s'), '共享背景\n\n场景规则')

    def test_pcm_encoding(self):
        event = json.loads(protocol.encode_audio(b'\0\1'))
        self.assertEqual(base64.b64decode(event['audio']), b'\0\1')

    def test_reject_cross_origin(self):
        from starlette.websockets import WebSocketDisconnect
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect('/api/doubao-realtime/ws', headers={'origin': 'https://other.example'}):
                pass
