"""Cold-start preparation must not capture audio or block API requests."""

import asyncio
import threading
import unittest
from unittest.mock import AsyncMock, Mock, patch

from backend.services.streaming_asr import StreamingASR


class RecordingStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_preparation_loads_filter_once_without_opening_microphone(self):
        asr = StreamingASR(preload=True)
        suppressor = Mock()
        with patch('backend.services.streaming_asr.create_noise_suppressor', return_value=suppressor) as create, \
             patch('backend.services.streaming_asr.pyaudio.PyAudio') as audio:
            asr.prepare_audio_processing()
            asr.prepare_audio_processing()
        create.assert_called_once()
        audio.assert_not_called()
        suppressor.process.assert_not_called()
        self.assertIs(asr._noise_suppressor, suppressor)
        self.assertFalse(asr.is_recording)
        self.assertIsNone(asr.ws_client)

    async def test_prepared_filter_is_reused_when_capture_opens(self):
        asr = StreamingASR(preload=True)
        asr.loop = asyncio.get_running_loop()
        asr.audio_queue = asyncio.Queue()
        audio = Mock()
        audio.get_default_input_device_info.return_value = {'name': 'Mic', 'index': 0}
        with patch('backend.services.streaming_asr.create_noise_suppressor', return_value=None) as create, \
             patch('backend.services.streaming_asr.pyaudio.PyAudio', return_value=audio):
            asr.prepare_audio_processing()
            await asyncio.to_thread(asr._start_audio_capture)
            await asyncio.to_thread(asr.capture_thread.join, 1)
        create.assert_called_once()
        audio.open.assert_called_once()
        self.assertIsNotNone(asr.recording_start_time)

    async def test_slow_device_open_keeps_loop_responsive_and_waits_for_capture(self):
        asr = StreamingASR()
        loop = asyncio.get_running_loop()
        entered = loop.create_future()
        release_device = threading.Event()
        ready = asyncio.create_task(asr.wait_until_recording())
        client = AsyncMock()
        client.ws = object()

        def open_device():
            loop.call_soon_threadsafe(entered.set_result, None)
            if not release_device.wait(timeout=2):
                raise RuntimeError('Device initialization blocked the event loop')

        with patch.object(asr, '_start_audio_capture', side_effect=open_device), \
             patch.object(asr, '_sender_loop', new_callable=AsyncMock), \
             patch.object(asr, '_receiver_loop', new_callable=AsyncMock), \
             patch('backend.services.streaming_asr.SonioxStreamingClient', return_value=client):
            asr.provider = 'soniox'
            startup = asyncio.create_task(asr.start_streaming())
            try:
                await asyncio.wait_for(entered, timeout=3)
                self.assertFalse(ready.done(), 'Ready must wait for device-open completion')
                release_device.set()
                await asyncio.wait_for(ready, timeout=3)
                await asyncio.wait_for(startup, timeout=3)
            finally:
                release_device.set()
                await asyncio.gather(startup, ready, return_exceptions=True)
        self.assertTrue(asr.connection_ready)

    async def test_device_open_error_releases_start_request(self):
        asr = StreamingASR()
        ready = asyncio.create_task(asr.wait_until_recording())
        with patch.object(asr, '_start_audio_capture', side_effect=OSError('Microphone unavailable')):
            startup = asyncio.create_task(asr.start_streaming())
            outcomes = await asyncio.wait_for(
                asyncio.gather(startup, ready, return_exceptions=True), timeout=3
            )
        self.assertIsInstance(outcomes[0], OSError)
        self.assertIsInstance(outcomes[1], RuntimeError)
        self.assertIn('Microphone unavailable', str(outcomes[1]))
        self.assertFalse(asr.is_recording)
        self.assertIsNone(asr.ws_client)


if __name__ == '__main__':
    unittest.main()
