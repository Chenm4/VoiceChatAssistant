import asyncio
import queue
import unittest
from unittest.mock import Mock, patch
from backend.services.streaming_asr import StreamingASR

class Stream:
    def __init__(self):
        self.frames = queue.Queue()
        self.waits = 0
        self.closed = False
    def read(self, *args, **kwargs):
        self.waits += 1
        return self.frames.get(timeout=1)
    def stop_stream(self): pass
    def close(self): self.closed = True

class DualInputTests(unittest.IsolatedAsyncioTestCase):
    async def wait_for(self, check):
        for _ in range(100):
            if check(): return
            await asyncio.sleep(.005)
        self.fail('capture worker did not consume expected frame')

    async def test_switch_keeps_both_devices_and_same_asr_and_only_routes_selected_audio(self):
        asr = StreamingASR(preload=True)
        asr.loop = asyncio.get_running_loop()
        asr.audio_queue = asyncio.Queue()
        asr.is_recording = True
        asr.input_device_index = 0
        asr.keep_other_input_open = True
        asr.standby_input_device_index = 1
        streams = [Stream(), Stream()]
        devices = [dict(index=0, name='Mic', maxInputChannels=1), dict(index=1, name='USB Audio', maxInputChannels=1)]
        audio = Mock()
        audio.get_device_info_by_index.side_effect = lambda index: devices[index]
        audio.open.side_effect = lambda **kwargs: streams[kwargs['input_device_index']]
        connection = object()
        asr.ws_client = connection
        asr.partial_text = 'USB此前识别的文字'
        chunks = [b'\x01\x00'*100, b'\x02\x00'*100, b'\x03\x00'*100]
        ignored_usb, ignored_mic = b'\x04\x00'*100, b'\x05\x00'*100
        with patch('backend.services.streaming_asr.pyaudio.PyAudio', return_value=audio), \
             patch('backend.services.streaming_asr.create_noise_suppressor', return_value=None):
            asr._start_audio_capture()
            try:
                streams[0].frames.put(chunks[0]); streams[1].frames.put(ignored_usb)
                await self.wait_for(lambda: streams[0].waits >= 2 and streams[1].waits >= 2)
                await asr.switch_input(1, 'USB Audio', 'usb')
                streams[1].frames.put(chunks[1]); streams[0].frames.put(ignored_mic)
                await self.wait_for(lambda: streams[0].waits >= 3 and streams[1].waits >= 3)
                await asr.switch_input(0, 'Mic', 'microphone')
                streams[0].frames.put(chunks[2])
                await self.wait_for(lambda: streams[0].waits >= 4)
                self.assertEqual(asr.audio_buffer, chunks)
                self.assertEqual(asr.partial_text, 'USB此前识别的文字')
                self.assertIs(asr.ws_client, connection)
                self.assertEqual(audio.open.call_count, 2)
                self.assertTrue(all(not stream.closed for stream in streams))
                self.assertEqual(asr.input_source, 'microphone')
            finally:
                asr.is_recording = False
                for stream in streams: stream.frames.put(b'')
                for thread in asr._capture_threads: await asyncio.to_thread(thread.join, .5)

    async def test_failed_switch_leaves_current_device_and_transcript_untouched(self):
        asr = StreamingASR()
        asr.is_recording = True
        asr.partial_text = '已有文字'
        asr.p = Mock()
        asr.p.get_device_info_by_index.side_effect = OSError('unplugged')
        asr.p.get_device_count.return_value = 0
        with self.assertRaises(ValueError):
            await asr.switch_input(1, 'USB Audio', 'usb')
        self.assertEqual(asr.partial_text, '已有文字')
        self.assertEqual(asr.input_source, 'microphone')
        self.assertTrue(asr.is_recording)


class MixedInputTests(DualInputTests):
    async def test_mixing_preserves_duration_and_usb_only_audio_reaches_asr(self):
        import struct
        asr = StreamingASR(preload=True)
        asr.loop = asyncio.get_running_loop()
        asr.audio_queue = asyncio.Queue()
        asr.is_recording = True
        asr.mix_inputs = True
        asr.input_device_index = 0
        asr.standby_input_device_index = 1
        asr.CHUNK = 100
        asr.bytes_per_segment = 200
        streams = [Stream(), Stream()]
        devices = [dict(index=i, name=name, maxInputChannels=1)
                   for i, name in enumerate(['Mic', 'USB Audio'])]
        audio = Mock()
        audio.get_device_info_by_index.side_effect = lambda index: devices[index]
        audio.open.side_effect = lambda **kwargs: streams[kwargs['input_device_index']]
        pcm = lambda value: struct.pack('<h', value) * 100
        with patch('backend.services.streaming_asr.pyaudio.PyAudio', return_value=audio), \
             patch('backend.services.streaming_asr.create_noise_suppressor', return_value=None):
            asr._start_audio_capture()
            try:
                for mic, usb in [(0, 12000), (32000, 32000), (-32000, -32000)]:
                    streams[1].frames.put(pcm(usb))
                    streams[0].frames.put(pcm(mic))
                    expected = pcm((mic + usb) // 2)
                    self.assertEqual(await asyncio.wait_for(asr.audio_queue.get(), .5), expected)
                self.assertEqual(len(b''.join(asr.audio_buffer)), 600)
                # Verify actual WAV frames are exactly the PCM consumed by ASR.
                import tempfile
                import wave
                from pathlib import Path
                real_open = wave.open
                with tempfile.TemporaryDirectory() as directory:
                    target = str(Path(directory) / 'mixed.wav')
                    with patch('backend.services.streaming_asr.wave.open',
                               side_effect=lambda path, mode: real_open(target, mode)):
                        self.assertIsNotNone(asr._save_wav_file())
                    with real_open(target, 'rb') as saved:
                        self.assertEqual(saved.getnchannels(), asr.CHANNELS)
                        self.assertEqual(saved.getframerate(), asr.RATE)
                        self.assertEqual(saved.readframes(saved.getnframes()),
                                         b''.join(asr.audio_buffer))
                self.assertGreater(asr.raw_peak, 0)
                # A missing secondary block must not stall microphone capture.
                streams[0].frames.put(pcm(1000))
                self.assertEqual(await asyncio.wait_for(asr.audio_queue.get(), .5), pcm(500))
                await asr.switch_input(1, 'USB Audio', 'usb')
                streams[1].frames.put(pcm(8000))
                self.assertEqual(await asyncio.wait_for(asr.audio_queue.get(), .5), pcm(8000))
            finally:
                asr.is_recording = False
                for stream in streams: stream.frames.put(b'')
                for thread in asr._capture_threads: await asyncio.to_thread(thread.join, .5)

    async def test_same_device_is_not_mixed_twice(self):
        asr = StreamingASR(preload=True)
        asr.loop = asyncio.get_running_loop()
        asr.audio_queue = asyncio.Queue()
        asr.is_recording = True
        asr.mix_inputs = True
        asr.input_device_index = asr.standby_input_device_index = 0
        stream = Stream()
        audio = Mock()
        audio.get_device_info_by_index.return_value = dict(index=0, name='Mic', maxInputChannels=1)
        audio.open.return_value = stream
        with patch('backend.services.streaming_asr.pyaudio.PyAudio', return_value=audio), \
             patch('backend.services.streaming_asr.create_noise_suppressor', return_value=None):
            asr._start_audio_capture()
            try:
                data = b'\x10\x00' * 100
                stream.frames.put(data)
                await self.wait_for(lambda: bool(asr.audio_buffer))
                self.assertEqual(asr.audio_buffer, [data])
                self.assertEqual(audio.open.call_count, 1)
            finally:
                asr.is_recording = False
                stream.frames.put(b'')
                for thread in asr._capture_threads: await asyncio.to_thread(thread.join, .5)
