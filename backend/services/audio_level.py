"""Display-only microphone level mapping; never modifies recognition audio."""
import audioop
import math
from collections import deque


class AudioLevelMeter:
    def __init__(self, sample_rate, channels=1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.history = deque()
        self.elapsed = 0.0

    def update(self, pcm):
        if not pcm:
            return 0.0
        # Ignore DC offset: it is not audible microphone activity.
        centered = audioop.bias(pcm, 2, -audioop.avg(pcm, 2))
        rms = audioop.rms(centered, 2)
        db = 20 * math.log10(max(rms, 1) / 32768.0)
        self.elapsed += len(pcm) / (2 * self.channels * self.sample_rate)
        self.history.append((self.elapsed, db))
        while self.history and self.history[0][0] < self.elapsed - 5:
            self.history.popleft()
        # Estimate background from the quietest frames, not the current peak.
        # Bound the estimate so continuous speech cannot raise the gate forever.
        gate = -50.0
        if self.elapsed >= .5:
            ordered = sorted(level for _, level in self.history)
            noise = ordered[int((len(ordered) - 1) * .1)]
            gate = max(-55.0, min(-35.0, noise) + 6.0)
        if db <= gate:
            return 0.0
        # Full scale is close to clipping (-3 dBFS), not 11% amplitude.
        return min(1.0, (db - gate) / (-3.0 - gate))
