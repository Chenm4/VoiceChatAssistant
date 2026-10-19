import audioop
import time

from backend.services.audio_level import AudioLevelMeter
from backend.services.streaming_asr import StreamingASR
from backend.services.user_workspace import user_config


def require_asr_credentials():
    provider = user_config('ASR_CONFIG').get('provider', 'soniox').lower()
    if provider == 'soniox':
        if not user_config('SONIOX_CONFIG').get('api_key'):
            raise ValueError('请先在设置中配置当前账号的 Soniox API Key')
    elif provider == 'volcengine':
        settings = user_config('VOLCENGINE_CONFIG')
        if not settings.get('appid') or not settings.get('token'):
            raise ValueError('请先在设置中配置当前账号的火山 ASR App ID 和 Token')
    else:
        raise ValueError('不支持的语音识别服务')


class BrowserStreamingASR(StreamingASR):
    def __init__(self):
        super().__init__()
        self.RATE = 16000
        self.CHANNELS = 1
        self.frames_per_segment = int(self.RATE * self.segment_duration / 1000)
        self.bytes_per_segment = self.frames_per_segment * 2
        self.input_device_name = '浏览器麦克风'
        self._browser_meter = AudioLevelMeter(self.RATE, self.CHANNELS)

    def _start_audio_capture(self):
        self.recording_start_time = time.time()

    def receive_pcm(self, data):
        if not self.is_recording or self._capture_end_sent:
            raise ValueError('录音已结束，请重新开始')
        if not data or len(data) % 2 or len(data) > 32000:
            raise ValueError('音频必须为不超过一秒的单声道 16kHz PCM16')
        if time.time() - self.recording_start_time >= self.max_duration_seconds:
            self.auto_stopped = True
            self.is_recording = False
            self._finish_capture()
            raise ValueError('录音已达到时长上限')
        if self.audio_queue.qsize() >= 10:
            raise ValueError('识别服务处理过慢，请停止录音后重试')
        with self._capture_lock:
            self.raw_peak = max(self.raw_peak, audioop.max(data, 2))
            self._append_pcm(data, self._browser_meter)
