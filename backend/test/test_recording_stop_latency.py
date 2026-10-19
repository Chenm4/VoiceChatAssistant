import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from backend.services.streaming_asr import StreamingASR
from backend.services.soniox_streaming import SonioxStreamingClient


class RecordingStopLatencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_flushes_tail_and_sends_eof_without_waiting_for_timeout(self):
        asr = StreamingASR(preload=True)
        asr.loop = asyncio.get_running_loop()
        asr.audio_queue = asyncio.Queue()
        asr.connection_ready = True
        asr.provider = 'soniox'
        asr.is_recording = True
        asr._pending_audio = b'\x01\x00' * 100
        sent = []
        responses = asyncio.Queue()

        class Socket:
            async def send(self, data):
                sent.append(data)
                if data == '':
                    await responses.put('{"tokens":[{"text":"完整结果","is_final":true}],"finished":true}')
            def __aiter__(self): return self
            async def __anext__(self): return await responses.get()
            async def close(self): pass

        asr.ws_client = SonioxStreamingClient(api_key='test')
        asr.ws_client.ws = Socket()

        async def run():
            await asyncio.gather(asr._sender_loop(), asr._receiver_loop())
        asr._task = asyncio.create_task(run())
        with patch.object(asr, '_save_wav_file', return_value=None):
            text, error = await asyncio.wait_for(asr.stop_streaming(), timeout=.5)
        self.assertEqual(text, '完整结果')
        self.assertIsNone(error)
        self.assertEqual(sent, [b'\x01\x00' * 100, ''])
        self.assertTrue(asr._task.done())
        asr._finish_capture()
        await asyncio.sleep(0)
        self.assertTrue(asr.audio_queue.empty(), 'EOF must only be sent once')

    async def test_completed_asr_with_only_partial_does_not_poll_for_three_seconds(self):
        asr = StreamingASR(preload=True)
        asr.audio_queue = asyncio.Queue()
        asr.partial_text = '保留临时结果'
        asr._task = asyncio.create_task(asyncio.sleep(0))
        asr.ws_client = SimpleNamespace(__aexit__=AsyncMock())
        with patch.object(asr, '_save_wav_file', return_value=None):
            text, error = await asyncio.wait_for(asr.stop_streaming(), timeout=.5)
        self.assertEqual(text, '保留临时结果')
        self.assertIsNone(error)

    async def test_final_response_timeout_returns_partial_after_one_second(self):
        import time
        asr = StreamingASR(preload=True)
        asr.audio_queue = asyncio.Queue()
        asr.partial_text = '一秒时已有的文字'
        asr._task = asyncio.create_task(asyncio.Event().wait())
        release_close = asyncio.Event()
        asr.ws_client = SimpleNamespace(__aexit__=AsyncMock(side_effect=lambda *args: None))
        async def slow_close(*args):
            await release_close.wait()
        asr.ws_client.__aexit__.side_effect = slow_close
        started = time.monotonic()
        try:
            with patch.object(asr, '_save_wav_file', return_value=None):
                text, error = await asyncio.wait_for(asr.stop_streaming(), timeout=1.4)
            elapsed = time.monotonic() - started
            self.assertGreaterEqual(elapsed, .9)
            self.assertLess(elapsed, 1.4)
            self.assertEqual(text, '一秒时已有的文字')
            self.assertIsNone(error)
            await asyncio.sleep(0)
            self.assertTrue(asr._task.cancelled())
        finally:
            release_close.set()
            await asyncio.sleep(.01)

    async def test_no_text_timeout_returns_failure_without_extra_polling(self):
        asr = StreamingASR(preload=True)
        asr.audio_queue = asyncio.Queue()
        asr._task = asyncio.create_task(asyncio.Event().wait())
        with patch.object(asr, '_save_wav_file', return_value=None):
            text, error = await asyncio.wait_for(asr.stop_streaming(), timeout=1.4)
        self.assertIsNone(text)
        self.assertIn('未获取到结果', error)
        await asyncio.sleep(0)
        self.assertTrue(asr._task.cancelled())
