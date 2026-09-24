"""Real-time microphone noise suppression for 16-bit mono PCM."""

import os


class NoiseSuppressor:
    """Apply noisereduce's non-stationary spectral gate to short PCM chunks.

    A short rolling history gives the noise estimator context while the output
    remains exactly one input chunk long, so the ASR packet timing is unchanged.
    Create a new instance for each recording to avoid carrying noise history
    between sessions.
    """

    def __init__(self, sample_rate: int, channels: int = 1) -> None:
        if channels != 1:
            raise ValueError("Noise suppression requires mono audio")
        import noisereduce
        import numpy as np

        self._reduce_noise = noisereduce.reduce_noise
        self._np = np
        self.sample_rate = sample_rate
        self.history_samples = int(sample_rate * 0.75)
        self._history = np.empty(0, dtype=np.int16)
        try:
            self.strength = float(os.getenv("AUDIO_NOISE_REDUCTION_STRENGTH", "0.3"))
        except ValueError as exc:
            raise ValueError("AUDIO_NOISE_REDUCTION_STRENGTH must be a number") from exc
        if not 0 <= self.strength <= 1:
            raise ValueError("AUDIO_NOISE_REDUCTION_STRENGTH must be between 0 and 1")

    def process(self, pcm: bytes) -> bytes:
        if not pcm:
            return pcm
        if len(pcm) % 2:
            raise ValueError("16-bit PCM must contain whole samples")

        samples = self._np.frombuffer(pcm, dtype="<i2")
        context = self._np.concatenate((self._history, samples))
        self._history = context[-self.history_samples:].copy()
        clean = self._reduce_noise(
            y=context,
            sr=self.sample_rate,
            stationary=False,
            prop_decrease=self.strength,
            time_constant_s=0.25,
            n_fft=512,
            n_jobs=1,
        )
        return clean[-len(samples):].astype("<i2", copy=False).tobytes()


def create_noise_suppressor(sample_rate: int, channels: int, logger):
    """Return a fresh suppressor, or log why unprocessed audio is used."""
    enabled = os.getenv("AUDIO_NOISE_REDUCTION", "true").strip().lower()
    if enabled in {"0", "false", "off", "no"}:
        logger.info("麦克风降噪已通过 AUDIO_NOISE_REDUCTION 关闭")
        return None
    try:
        suppressor = NoiseSuppressor(sample_rate, channels)
    except Exception as exc:
        logger.warning("麦克风降噪不可用，将发送原始音频: %s", exc)
        return None
    logger.info("麦克风降噪已启用: noisereduce 非平稳谱门算法，强度 %.2f", suppressor.strength)
    return suppressor
