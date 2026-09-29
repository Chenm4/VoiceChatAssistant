import asyncio
import time
import unittest
from unittest.mock import Mock, patch
from backend.services.streaming_asr import StreamingASR
from backend.api import routes


class RecordingMeterTests(unittest.IsolatedAsyncioTestCase):
    async def capture(self, frames, devices=None):
        asr = StreamingASR(preload=True)
        asr.is_recording = True
        asr.loop = asyncio.get_running_loop()
        asr.audio_queue = asyncio.Queue()
        audio = Mock()
        devices = devices or [{'index': 0, 'name': 'Mic', 'maxInputChannels': 1}]
        audio.get_device_count.return_value = len(devices)
        audio.get_device_info_by_index.side_effect = lambda index: devices[index]
        audio.get_default_input_device_info.return_value = devices[0]
        asr.input_device_index = 0
        asr.requested_device_name = 'Mic'
        remaining = iter(frames)
        def read(*args, **kwargs):
            frame = next(remaining)
            if isinstance(frame, Exception):
                raise frame
            if frame == b'\0\0' * 960:
                asr.is_recording = False
            return frame
        audio.open.return_value.read.side_effect = read
        with patch('backend.services.streaming_asr.pyaudio.PyAudio', return_value=audio), patch('backend.services.streaming_asr.create_noise_suppressor', return_value=None):
            asr._start_audio_capture()
            await asyncio.to_thread(asr.capture_thread.join, 2)
            await asyncio.sleep(0)
        self.assertFalse(asr.capture_thread.is_alive())
        return asr, audio

    async def test_level_returns_to_zero_after_speech(self):
        asr, audio = await self.capture([b'\x34\x12' * 960, b'\0\0' * 960])
        self.assertGreater(asr.raw_peak, 0)
        self.assertEqual(asr.audio_level, 0)

    async def test_device_index_change_recovers_same_named_mic(self):
        asr, audio = await self.capture([b'\0\0' * 960], [
            {'index': 0, 'name': 'Other', 'maxInputChannels': 1},
            {'index': 1, 'name': 'Mic', 'maxInputChannels': 1},
        ])
        self.assertEqual(audio.open.call_args.kwargs['input_device_index'], 1)
        self.assertEqual(asr.input_device_name, 'Mic')

    async def test_read_failure_stops_recording_and_is_reported(self):
        asr, audio = await self.capture([OSError('Device disconnected')])
        self.assertFalse(asr.is_recording)
        self.assertEqual(asr.audio_level, 0)
        self.assertIn('Device disconnected', asr.error_message)
        self.assertIsNone(asr.audio_queue.get_nowait())

    async def test_status_meter_fresh_stale_and_stopped(self):
        asr = StreamingASR(preload=True)
        asr.is_recording = True
        asr.audio_level = .6
        asr.raw_peak = 2000
        asr.last_audio_at = time.monotonic()
        with patch.object(routes, 'streaming_asr', asr):
            self.assertEqual((await routes.get_recording_status())['audio_level'], .6)
            asr.last_audio_at -= 1
            self.assertEqual((await routes.get_recording_status())['audio_level'], 0)
            asr.last_audio_at = time.monotonic()
            asr.is_recording = False
            self.assertEqual((await routes.get_recording_status())['audio_level'], 0)

    async def test_silent_capture_warning(self):
        asr = StreamingASR(preload=True)
        asr.is_recording = True
        asr.recording_start_time = time.time() - 5
        asr.input_device_name = 'Mic'
        with patch.object(routes, 'streaming_asr', asr):
            self.assertIn('Mic', (await routes.get_recording_status())['capture_warning'])
            asr.raw_peak = 2000
            self.assertIsNone((await routes.get_recording_status())['capture_warning'])
