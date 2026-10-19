"""Checks for the microphone noise reduction path."""

from backend.test.workspace_case import WorkspaceTestCase, workspace

import logging
import os
import unittest
from unittest.mock import patch

import numpy as np

from backend.services.noise_suppression import NoiseSuppressor, create_noise_suppressor


class NoiseSuppressionTests(WorkspaceTestCase):
    def test_streaming_chunks_preserve_length_and_reduce_noise(self):
        sample_rate = 16000
        rng = np.random.default_rng(42)
        time = np.arange(sample_rate) / sample_rate
        speech = 5000 * np.sin(2 * np.pi * 440 * time)
        noisy = np.clip(speech + rng.normal(0, 1800, sample_rate), -32768, 32767).astype("<i2")

        suppressor = NoiseSuppressor(sample_rate)
        chunks = np.array_split(noisy, 17)
        clean = np.concatenate([
            np.frombuffer(suppressor.process(chunk.tobytes()), dtype="<i2")
            for chunk in chunks
        ])

        self.assertEqual(clean.dtype, noisy.dtype)
        self.assertEqual(len(clean), len(noisy))

        # Check that the speech component remains audible while broadband
        # residual noise falls; a silent output would fail this test.
        reference = np.sin(2 * np.pi * 440 * time)
        def components(audio):
            amplitude = 2 * np.dot(audio, reference) / sample_rate
            residual = np.sqrt(np.mean((audio - amplitude * reference) ** 2))
            return amplitude, residual

        before_speech, before_noise = components(noisy.astype(float))
        after_speech, after_noise = components(clean.astype(float))
        self.assertGreater(after_speech, before_speech * 0.7)
        self.assertLess(after_noise, before_noise * 0.9)

    def test_can_disable_noise_reduction(self):
        with patch.dict(workspace().settings['NOISE_REDUCTION'], {'enabled': False}):
            self.assertIsNone(create_noise_suppressor(16000, 1, logging.getLogger(__name__)))

    def test_rejects_partial_pcm_sample(self):
        with self.assertRaises(ValueError):
            NoiseSuppressor(16000).process(b"\x01")


if __name__ == "__main__":
    unittest.main()
