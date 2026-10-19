from backend.test.workspace_case import WorkspaceAsyncTestCase, user_state
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from backend.services.streaming_asr import StreamingASR
from backend.api import routes

class CancelRecordingTests(WorkspaceAsyncTestCase):
    async def test_cancel_keeps_partial_text_without_waiting_for_final_tokens_or_queue(self):
        asr = StreamingASR()
        asr.partial_text = 'USB 已识别内容，麦克风追加内容'
        asr.audio_queue = asyncio.Queue()
        await asr.audio_queue.put(b'pending audio')
        asr._task = asyncio.create_task(asyncio.Event().wait())
        asr.ws_client = SimpleNamespace(__aexit__=AsyncMock())
        with patch.object(asr, '_save_wav_file', return_value=None):
            text, error = await asyncio.wait_for(asr.stop_streaming(finalize=False), timeout=.5)
        self.assertEqual(text, 'USB 已识别内容，麦克风追加内容')
        self.assertIsNone(error)
        self.assertTrue(asr._task.cancelled())
        self.assertFalse(asr.is_recording)
        asr.ws_client.__aexit__.assert_awaited_once()

    async def test_cancel_endpoint_passes_fast_mode_and_returns_preserved_draft(self):
        stop = AsyncMock(return_value=('已识别草稿', None))
        current = SimpleNamespace(stop_streaming=stop, session_id='s', saved_audio_file=None)
        with patch.object(user_state(), 'streaming_asr', current), patch.object(routes, 'attach_recording_to_session'):
            result = await routes.stop_recording(finalize=False)
        stop.assert_awaited_once_with(finalize=False)
        self.assertTrue(result.success)
        self.assertEqual(result.text, '已识别草稿')
