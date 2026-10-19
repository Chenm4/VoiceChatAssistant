import struct
import unittest
from backend.services.audio_level import AudioLevelMeter


def pcm(amplitude):
    return struct.pack('<hh', amplitude, -amplitude) * 480


class AudioLevelTests(unittest.TestCase):
    def test_silence_and_dc_offset_are_zero(self):
        meter = AudioLevelMeter(16000)
        self.assertEqual(meter.update(pcm(0)), 0)
        self.assertEqual(meter.update(struct.pack('<h', 12000) * 960), 0)

    def test_background_noise_is_gated_then_speech_rises(self):
        meter = AudioLevelMeter(16000)
        for _ in range(20):
            level = meter.update(pcm(730))
        self.assertEqual(level, 0)
        speech = meter.update(pcm(3200))
        loud = meter.update(pcm(12000))
        self.assertGreater(speech, 0)
        self.assertLess(speech, loud)
        self.assertLess(loud, 1)
        self.assertEqual(meter.update(pcm(730)), 0)

    def test_old_saturation_point_no_longer_fills_meter(self):
        meter = AudioLevelMeter(16000)
        self.assertLess(meter.update(pcm(3641)), .7)
        self.assertEqual(meter.update(pcm(30000)), 1)

    def test_quiet_speech_after_quiet_room_still_registers(self):
        meter = AudioLevelMeter(16000)
        for _ in range(20):
            meter.update(pcm(40))
        self.assertGreater(meter.update(pcm(250)), 0)
