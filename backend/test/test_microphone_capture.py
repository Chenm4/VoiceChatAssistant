import asyncio
import unittest
from unittest.mock import Mock, patch

from backend.services.streaming_asr import StreamingASR


class MicrophoneCaptureTests(unittest.IsolatedAsyncioTestCase):
    async def capture(self, pcm, selected_index=None):
        asr = StreamingASR(preload=True)
        asr.input_device_index = selected_index
        asr.requested_device_name = 'Selected mic' if selected_index is not None else None
        asr.is_recording = True
        asr.loop = asyncio.get_running_loop()
        asr.audio_queue = asyncio.Queue()
        device = Mock()
        device.get_default_input_device_info.return_value = {'name': 'Current mic', 'index': 4}
        device.get_device_info_by_index.return_value = {'name': 'Selected mic', 'index': selected_index, 'maxInputChannels': 1}
        stream = device.open.return_value
        def read(*args, **kwargs):
            asr.is_recording = False
            return pcm
        stream.read.side_effect = read
        with patch('backend.services.streaming_asr.pyaudio.PyAudio', return_value=device), \
             patch('backend.services.streaming_asr.create_noise_suppressor', return_value=None):
            asr._start_audio_capture()
            await asyncio.to_thread(asr.capture_thread.join, 2)
            await asyncio.sleep(0)
        self.assertEqual(device.open.call_args.kwargs['input_device_index'], selected_index if selected_index is not None else 4)
        if selected_index is not None:
            device.get_default_input_device_info.assert_not_called()
        self.assertEqual(asr.audio_buffer, [pcm])
        return asr

    async def test_explicit_microphone_including_index_zero(self):
        asr = await self.capture(b'\x34\x12' * 960, selected_index=0)
        self.assertEqual(asr.input_device_name, 'Selected mic')
        asr.stream.close()
        asr.p.terminate()

    async def test_changed_device_is_rejected_before_capture(self):
        asr = StreamingASR(preload=True)
        asr.input_device_index = 2
        asr.requested_device_name = 'Selected mic'
        device = Mock()
        device.get_device_info_by_index.return_value = {'name': 'Other mic', 'index': 2, 'maxInputChannels': 1}
        with patch('backend.services.streaming_asr.pyaudio.PyAudio', return_value=device), \
             patch('backend.services.streaming_asr.create_noise_suppressor', return_value=None):
            with self.assertRaisesRegex(Exception, '重新选择'):
                asr._start_audio_capture()
        device.open.assert_not_called()
        device.terminate()

    async def test_current_device_and_nonzero_audio(self):
        with patch('backend.services.streaming_asr.pyaudio.PyAudio') as factory:
            StreamingASR(preload=True)
            factory.assert_not_called()
        asr = await self.capture(b'\x34\x12' * 960)
        self.assertEqual(asr.raw_peak, 0x1234)
        self.assertEqual(asr.processed_peak, 0x1234)
        asr.stream.close()
        asr.p.terminate()

    async def test_silence_is_reported_as_capture_failure(self):
        asr = await self.capture(b'\0\0' * 960)
        while not asr.audio_queue.empty():
            asr.audio_queue.get_nowait()
        asr.error_message = '未检测到有效语音内容'
        with patch.object(asr, '_save_wav_file', return_value=None):
            text, error = await asr.stop_streaming()
        self.assertIsNone(text)
        self.assertIn('Current mic', error)
        self.assertIn('全为静音', error)
