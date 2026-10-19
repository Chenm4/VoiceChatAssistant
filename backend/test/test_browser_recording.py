import asyncio
import struct
import wave
from unittest.mock import patch

from workspace_case import WorkspaceAsyncTestCase
from backend.api.voice_settings import VoiceSettings, get_voice_settings, save_voice_settings
from backend.services.browser_recording import BrowserStreamingASR, require_asr_credentials
from backend.services.user_workspace import user_config, user_state


class BrowserRecordingTest(WorkspaceAsyncTestCase):
    async def test_browser_capture_never_opens_server_microphone_and_saves_pcm(self):
        recorder = BrowserStreamingASR()
        recorder.loop = asyncio.get_running_loop()
        recorder.audio_queue = asyncio.Queue()
        recorder.is_recording = True
        with patch('backend.services.streaming_asr.pyaudio.PyAudio', side_effect=AssertionError('server microphone opened')):
            recorder._start_audio_capture()
        pcm = struct.pack('<3200h', *([800, -800] * 1600))
        recorder.receive_pcm(pcm)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertEqual(await asyncio.wait_for(recorder.audio_queue.get(), 1), pcm)
        saved = recorder._save_wav_file()
        with wave.open(saved, 'rb') as audio:
            self.assertEqual((audio.getframerate(), audio.getnchannels(), audio.getsampwidth()), (16000, 1, 2))
            self.assertEqual(audio.readframes(3200), pcm)

    async def test_rejects_invalid_pcm_and_audio_after_stop(self):
        recorder = BrowserStreamingASR()
        recorder._start_audio_capture()
        recorder.is_recording = True
        recorder.audio_queue = asyncio.Queue()
        for invalid in (b'', b'\x01', b'\0' * 32002):
            with self.assertRaises(ValueError):
                recorder.receive_pcm(invalid)
        for index in range(10):
            recorder.audio_queue.put_nowait(b'\0\0')
        with self.assertRaisesRegex(ValueError, '处理过慢'):
            recorder.receive_pcm(b'\0\0')
        recorder.is_recording = False
        with self.assertRaisesRegex(ValueError, '录音已结束'):
            recorder.receive_pcm(b'\0\0')
        self.assertEqual(recorder.audio_buffer, [])

    async def test_missing_key_is_reported_before_starting_capture(self):
        with self.assertRaisesRegex(ValueError, 'Soniox API Key'):
            require_asr_credentials()

    async def test_voice_settings_persist_to_authenticated_workspace(self):
        await save_voice_settings(VoiceSettings(soniox_api_key='my-soniox', doubao_app_id='my-app', doubao_access_token='my-token'))
        saved = await get_voice_settings()
        self.assertEqual(saved.soniox_api_key, 'my-soniox')
        self.assertEqual(user_config('DOUBAO_REALTIME')['access_token'], 'my-token')
        user_state().streaming_asr = object()
        with self.assertRaises(Exception) as rejected:
            await save_voice_settings(VoiceSettings())
        self.assertEqual(rejected.exception.status_code, 409)
