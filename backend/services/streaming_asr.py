"""
实时流式语音识别服务

提供边录音边识别的实时语音识别功能，无需等待录音完成。
支持预热模式，可提前初始化实例以加速启动。

特性：
- 实时流式识别：边录音边发送音频数据
- 预热支持：提前创建实例，加速首次录音启动
- 自动保存：录音自动保存为 WAV 文件
"""

import asyncio
import audioop
import queue
import sys
import threading
import time
import wave
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import pyaudio

sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.utils.logger import get_asr_logger
from backend.services.noise_suppression import create_noise_suppressor
from backend.services.audio_level import AudioLevelMeter
from backend.services.volcengine_streaming import VolcengineStreamingClient
from backend.services.soniox_streaming import SonioxStreamingClient
from config import AUDIO_CONFIG, ASR_CONFIG, SONIOX_CONFIG, VOLCENGINE_CONFIG



_connection_cleanup_tasks = set()


def mix_pcm16(first: bytes, second: bytes) -> bytes:
    """Equal-gain mixing with headroom; preserve the input frame count."""
    if len(first) != len(second):
        raise ValueError('PCM blocks must have equal lengths')
    return audioop.add(audioop.mul(first, 2, 0.5), audioop.mul(second, 2, 0.5), 2)


class StreamingASR:
    """
    实时流式语音识别
    
    支持边录音边识别，无需等待录音完成。
    提供预热模式，可提前初始化实例以加速启动。
    
    Attributes:
        is_recording: 是否正在录音
        audio_queue: 音频数据队列
        result_text: 识别结果文本
        error_message: 错误信息
        ws_client: WebSocket 客户端
        stream: PyAudio 音频流
        p: PyAudio 实例
        loop: 事件循环引用
        connection_ready: 连接是否就绪
        audio_buffer: 音频数据缓冲区
        preloaded: 是否预热模式
        logger: 日志记录器
        
    Example:
        >>> # 预热模式
        >>> asr = StreamingASR(preload=True)
        >>> await asr.start_streaming()
        >>> # 录音中...
        >>> text, error = await asr.stop_streaming()
    """
    
    def __init__(self, preload: bool = False) -> None:
        """
        初始化流式识别实例
        
        Args:
            preload: 是否预热模式（只初始化结构，不打开麦克风）
                    预热模式可以提前创建实例，加速首次录音启动
        """
        self.logger = get_asr_logger()
        # 状态变量
        self.is_recording: bool = False
        self.audio_queue: Optional[asyncio.Queue] = None
        self.result_text: str = ""
        self.partial_text: str = ""
        self.error_message: Optional[str] = None
        self.ws_client: Optional[VolcengineStreamingClient] = None
        self.stream: Optional[pyaudio.Stream] = None
        self.p: Optional[pyaudio.PyAudio] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.connection_ready: bool = False
        self.audio_buffer: list = []
        self.preloaded: bool = preload
        self.recording_start_time: Optional[float] = None  # 录音开始时间
        self.saved_audio_file: Optional[str] = None
        self.max_duration_seconds: int = AUDIO_CONFIG.get('max_duration_minutes', 5) * 60  # 最大录音时长（秒）
        self.auto_stopped: bool = False  # 是否因超时自动停止
        self.provider: str = ASR_CONFIG.get('provider', 'soniox').lower()
        
        # 音频参数
        self.CHUNK: int = AUDIO_CONFIG['chunk']
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS: int = AUDIO_CONFIG['channels']
        self.RATE: int = AUDIO_CONFIG['rate']
        
        # 音频分段参数。两个后端都使用 16-bit PCM，并通过持久连接流式传输。
        self.url: str = VOLCENGINE_CONFIG.get('ws_url', 'wss://openspeech.bytedance.com/api/v2/asr')
        self.segment_duration: int = (
            VOLCENGINE_CONFIG.get('segment_duration', 200)
            if self.provider == 'volcengine'
            else 200
        )
        
        # 计算每个音频包的大小（字节数）
        # segment_duration (200ms) -> 每包需要多少帧
        self.frames_per_segment: int = int(self.RATE * self.segment_duration / 1000)
        self.bytes_per_segment: int = self.frames_per_segment * self.CHANNELS * 2
        
        # Do not keep a PortAudio device snapshot between recordings. The default
        # input may change while a preloaded ASR instance is waiting in the pool.
        self.input_device_name = ""
        self.input_device_index = None
        self.requested_device_name = None
        self.raw_peak = 0
        self.processed_peak = 0
        self.audio_level = 0.0
        self.last_audio_at = 0.0
        self._noise_suppressor = None
        self._audio_processing_ready = False
        self._capture_ready: Optional[asyncio.Event] = None
        self._input_streams = {}
        self._capture_threads = []
        self._active_device_index = None
        self._capture_lock = threading.Lock()
        self._device_open_lock = threading.Lock()
        self._pending_audio = b''
        self._capture_end_sent = False
        self.mix_inputs = False
        self._input_frames = {}
        self.keep_other_input_open = False
        self.standby_input_device_index = None
        self.standby_input_device_name = None
        self.input_source = 'microphone'
        self.input_errors = {}

        if preload:
            self.logger.info(
                f"🔥 [预热完成] ASR实例预热: {self.CHANNELS}声道, "
                f"{self.RATE}Hz, 每段{self.segment_duration}ms"
            )
            self.logger.info(
                f"🔥 [预热参数] {self.frames_per_segment}帧/段, "
                f"{self.bytes_per_segment}字节/段"
            )
        else:
            self.logger.info(
                f"初始化实时 ASR: {self.CHANNELS}声道, "
                f"{self.RATE}Hz, 每段{self.segment_duration}ms"
            )
            self.logger.info(
                f"每段参数: {self.frames_per_segment}帧, "
                f"{self.bytes_per_segment}字节"
            )

    def prepare_audio_processing(self):
        """Load dependencies and a fresh filter without opening a microphone."""
        if not self._audio_processing_ready:
            self._noise_suppressor = create_noise_suppressor(
                self.RATE, self.CHANNELS, self.logger
            )
            self._audio_processing_ready = True

    async def wait_until_recording(self):
        """Wait for the actual device-open result, not an assumed 50 ms delay."""
        if self._capture_ready is None:
            self._capture_ready = asyncio.Event()
        await self._capture_ready.wait()
        if self.error_message:
            raise RuntimeError(self.error_message)
    
    async def start_streaming(self):
        """
        开始实时流式识别（优化版：先录音，后建连 + 预热支持）
        1. 立即启动录音线程（缓冲音频）
        2. 并行建立 WebSocket 连接
        3. 发送配置请求
        4. 标记连接就绪，开始发送缓冲的音频
        """
        start_time = time.time()
        if self._capture_ready is None:
            self._capture_ready = asyncio.Event()
        self.logger.info("=" * 80)
        if self.preloaded:
            self.logger.info("🚀 [实时识别] 开始启动（预热实例，加速启动）...")
        else:
            self.logger.info("🚀 [实时识别] 开始启动（优化版：先录音）...")
        self.logger.info("=" * 80)
        
        try:
            # 保存当前事件循环引用（给线程使用）
            self.loop = asyncio.get_running_loop()
            
            # 创建异步队列（需要事件循环）
            if not self.audio_queue:
                self.audio_queue = asyncio.Queue()
            
            self.logger.info(f"📌 [事件循环] 保存事件循环引用: {self.loop}")
            
            # 1. 立即启动录音线程（最高优先级）
            record_start = time.time()
            self.logger.info("🎤 [立即启动录音] 开始录音线程（同时建立连接）...")
            
            self.is_recording = True
            # CoreAudio/PortAudio can take seconds on a cold device. Keep the
            # API event loop responsive while the worker opens the microphone.
            await asyncio.to_thread(self._start_audio_capture)
            self._capture_ready.set()
            
            record_elapsed = (time.time() - record_start) * 1000
            self.logger.info(f"✅ [录音已启动] 耗时: {record_elapsed:.2f}ms (音频正在缓冲)")
            
            # 2. 建立 WebSocket 连接（录音已经在进行中）
            connect_start = time.time()
            self.logger.info("🔗 [建立连接] 正在连接到 ASR 服务（录音已开始）...")
            
            if self.provider == 'soniox':
                self.ws_client = SonioxStreamingClient(
                    api_key=SONIOX_CONFIG['api_key'],
                    ws_url=SONIOX_CONFIG.get('ws_url'),
                    model=SONIOX_CONFIG['model'],
                    sample_rate=self.RATE,
                    num_channels=self.CHANNELS,
                    language=SONIOX_CONFIG.get('language', 'zh'),
                    context=SONIOX_CONFIG.get('context'),
                )
            elif self.provider == 'volcengine':
                self.ws_client = VolcengineStreamingClient(
                    appid=VOLCENGINE_CONFIG['appid'],
                    token=VOLCENGINE_CONFIG['token'],
                    cluster=VOLCENGINE_CONFIG['cluster'],
                    ws_url=self.url,
                    segment_duration=self.segment_duration
                )
            else:
                raise ValueError(
                    f"不支持的 ASR_PROVIDER: {self.provider}。可选值为 soniox 或 volcengine"
                )
            endpoint = (
                SONIOX_CONFIG.get('ws_url')
                if self.provider == 'soniox'
                else self.url
            )
            self.logger.info(
                f"📝 [创建客户端] provider={self.provider}, URL={endpoint}, "
                f"segment_duration={self.segment_duration}ms"
            )
            
            await self.ws_client.__aenter__()  # 初始化后端资源
            self.logger.info(f"✅ [Session创建] {self.provider} ASR 资源已初始化")
            
            await self.ws_client.create_connection()
            # Both adapters currently expose a websocket as ``ws``. Keep this
            # provider-neutral logging so a future adapter does not break
            # startup merely because it uses a different connection field.
            connection = getattr(self.ws_client, 'ws', None)
            if connection is None:
                connection = getattr(self.ws_client, '_client', None)
            self.logger.info(
                f"✅ [ASR连接] provider={self.provider}, "
                f"connection={'ready' if connection is not None else 'created'}"
            )
            
            connect_elapsed = (time.time() - connect_start) * 1000
            self.logger.info(f"✅ [连接成功] 耗时: {connect_elapsed:.2f}ms")
            
            # 3. 发送初始配置请求
            config_start = time.time()
            self.logger.info("📨 [发送配置] 发送初始配置请求...")
            
            await self.ws_client.send_full_client_request()
            
            config_elapsed = (time.time() - config_start) * 1000
            self.logger.info(f"✅ [配置成功] 耗时: {config_elapsed:.2f}ms")
            
            # 4. 标记连接就绪，发送循环开始发送缓冲的音频
            self.connection_ready = True
            self.logger.info(f"🎯 [连接就绪] 开始发送缓冲的音频数据（队列大小: {self.audio_queue.qsize()}）")
            
            total_startup = (time.time() - start_time) * 1000
            self.logger.info(f"🏁 [启动完成] 总耗时: {total_startup:.2f}ms (录音启动耗时: {record_elapsed:.2f}ms)")
            self.logger.info("=" * 80)
            
            # 5. 启动发送和接收任务
            sender_task = asyncio.create_task(self._sender_loop())
            receiver_task = asyncio.create_task(self._receiver_loop())
            
            # 等待任务完成（正常情况下会一直运行，直到调用 stop）
            await asyncio.gather(sender_task, receiver_task, return_exceptions=True)
            
        except Exception as e:
            total_elapsed = (time.time() - start_time) * 1000
            self.logger.error(f"❌ [启动失败] 耗时: {total_elapsed:.2f}ms - {e}", exc_info=True)
            self.error_message = f"启动实时识别失败: {str(e)}"
            self.is_recording = False
            self._capture_ready.set()
            raise
    
    def _resolve_input_device(self, index, name):
        if index is None and not name:
            return self.p.get_default_input_device_info()
        try:
            device = self.p.get_device_info_by_index(index) if index is not None else None
        except (OSError, ValueError):
            device = None
        if device is not None and device['maxInputChannels'] > 0 and (not name or device['name'] == name):
            return device
        matches = [self.p.get_device_info_by_index(i) for i in range(self.p.get_device_count())]
        matches = [device for device in matches if device['maxInputChannels'] > 0 and name and device['name'] == name]
        if len(matches) != 1:
            raise ValueError('所选麦克风已不可用，请刷新列表并重新选择')
        return matches[0]

    def _open_input(self, index, name, activate=False):
        with self._device_open_lock:
            device = self._resolve_input_device(index, name)
            device_index = int(device['index'])
            if device_index in self.input_errors and device_index in self._input_streams:
                self._input_streams.pop(device_index).close()
                self.input_errors.pop(device_index, None)
            if device_index not in self._input_streams:
                stream = self.p.open(format=self.FORMAT, channels=self.CHANNELS, rate=self.RATE,
                    input=True, input_device_index=device_index, frames_per_buffer=self.CHUNK)
                self._input_streams[device_index] = stream
                self._input_frames[device_index] = queue.Queue(maxsize=2)
                thread = threading.Thread(target=self._capture_input, args=(device_index, stream), daemon=True)
                self._capture_threads.append(thread)
                if activate:
                    self._activate_input(device, stream)
                thread.start()
            elif activate:
                self._activate_input(device, self._input_streams[device_index])
            return device

    def _activate_input(self, device, stream):
        with self._capture_lock:
            self._active_device_index = int(device['index'])
            self.input_device_index = int(device['index'])
            self.input_device_name = device['name']
            self.stream = stream
            self.audio_level = 0.0
            self.last_audio_at = 0.0

    async def switch_input(self, index, name, source, mix_inputs=False):
        if not self.is_recording:
            raise ValueError('当前未在识别，请先开始录音')
        device = await asyncio.to_thread(self._open_input, index, name, True)
        with self._capture_lock:
            self.mix_inputs = mix_inputs
            self.input_source = source
            for frames in self._input_frames.values():
                while not frames.empty():
                    try: frames.get_nowait()
                    except queue.Empty: break
        return device

    def _start_audio_capture(self):
        self.prepare_audio_processing()
        if self.p:
            self.p.terminate()
        self.p = pyaudio.PyAudio()
        self.recording_start_time = time.time()
        self.raw_peak = self.processed_peak = 0
        self._open_input(self.input_device_index, self.requested_device_name, True)
        self.capture_thread = self._capture_threads[0]
        if self.keep_other_input_open or self.mix_inputs:
            try:
                self._open_input(self.standby_input_device_index, self.standby_input_device_name)
            except Exception as error:
                if self.mix_inputs:
                    raise ValueError(f'混音的第二路输入无法打开: {error}') from error
                # An unavailable standby must not interrupt the selected input.
                self.logger.warning('备用录音设备未打开: %s', error)

    def _capture_input(self, device_index, stream):
        level_meter = AudioLevelMeter(self.RATE, self.CHANNELS)
        while self.is_recording:
            try:
                if self.recording_start_time and time.time() - self.recording_start_time >= self.max_duration_seconds:
                    self.auto_stopped = True
                    self.is_recording = False
                    break
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                if not data:
                    raise OSError('麦克风未返回音频数据')
                # The selected device is the clock: one output block per input
                # block, never concatenate two sources into twice the duration.
                if device_index != self._active_device_index:
                    if self.mix_inputs:
                        frames = self._input_frames[device_index]
                        try: frames.put_nowait((time.monotonic(), data))
                        except queue.Full:
                            try: frames.get_nowait()
                            except queue.Empty: pass
                            frames.put_nowait((time.monotonic(), data))
                    continue
                other_data = None
                if self.mix_inputs:
                    others = [index for index in self._input_frames if index != device_index]
                    if others:
                        frames = self._input_frames[others[0]]
                        # Bound skew/latency; a stalled source contributes silence.
                        deadline = time.monotonic() + self.CHUNK / self.RATE
                        while time.monotonic() < deadline:
                            try:
                                captured_at, candidate = frames.get(timeout=max(0, deadline - time.monotonic()))
                            except queue.Empty:
                                break
                            if time.monotonic() - captured_at <= 2 * self.CHUNK / self.RATE:
                                other_data = candidate
                                break
                with self._capture_lock:
                    if device_index != self._active_device_index or self._capture_end_sent:
                        continue
                    self.raw_peak = max(self.raw_peak, audioop.max(data, 2))
                    self.last_audio_at = time.monotonic()
                    if self._noise_suppressor is not None:
                        try:
                            data = self._noise_suppressor.process(data)
                        except Exception as error:
                            self.logger.warning('麦克风降噪失败: %s', error)
                            self._noise_suppressor = None
                    if self.mix_inputs and len(self._input_streams) > 1:
                        other_data = (other_data or b'')[:len(data)].ljust(len(data), b'\0')
                        self.raw_peak = max(self.raw_peak, audioop.max(other_data, 2))
                        data = mix_pcm16(data, other_data)
                    self.audio_level = level_meter.update(data)
                    self.processed_peak = max(self.processed_peak, audioop.max(data, 2))
                    self.audio_buffer.append(data)
                    self._pending_audio += data
                    while len(self._pending_audio) >= self.bytes_per_segment:
                        segment, self._pending_audio = self._pending_audio[:self.bytes_per_segment], self._pending_audio[self.bytes_per_segment:]
                        asyncio.run_coroutine_threadsafe(self.audio_queue.put(segment), self.loop)
            except Exception as error:
                if not self.is_recording:
                    break
                with self._capture_lock:
                    self.input_errors[device_index] = str(error)
                    if device_index == self._active_device_index or self.mix_inputs:
                        self.error_message = f'麦克风采集失败: {error}'
                        self.is_recording = False
                        self.audio_level = 0.0
                break
        if not self.is_recording and device_index == self._active_device_index:
            self._finish_capture()

    def _finish_capture(self):
        """Queue the final short block and exactly one EOF, even after device failure.

        Called by the capture worker or stop fallback. The lock also prevents
        a late device read from appending audio after EOF or after WAV saving.
        """
        with self._capture_lock:
            if self._capture_end_sent:
                return
            self._capture_end_sent = True
            if self.loop is None or self.audio_queue is None:
                return
            if self._pending_audio:
                asyncio.run_coroutine_threadsafe(self.audio_queue.put(self._pending_audio), self.loop)
                self._pending_audio = b''
            asyncio.run_coroutine_threadsafe(self.audio_queue.put(None), self.loop)
            self.logger.info('录音尾包与结束标记已入队')

    async def _sender_loop(self):
        """发送循环：从队列获取音频数据并发送（等待连接就绪）"""
        self.logger.info("📤 [发送循环] 启动...")
        
        # 等待连接就绪
        self.logger.info("⏳ [等待连接] 等待 WebSocket 连接就绪...")
        wait_start = time.time()
        while not self.connection_ready:
            await asyncio.sleep(0.01)  # 每10ms检查一次
        wait_elapsed = (time.time() - wait_start) * 1000
        self.logger.info(f"✅ [连接就绪] 等待耗时: {wait_elapsed:.2f}ms, 开始发送缓冲数据（队列大小: {self.audio_queue.qsize()}）")
        
        segment_count = 0
        total_bytes = 0
        send_start = time.time()
        
        try:
            while True:
                # 从队列获取音频数据
                audio_data = await self.audio_queue.get()
                
                # None 表示录音结束
                if audio_data is None:
                    self.logger.info("🏁 [发送循环] 收到结束标记，发送最后一个包（is_last=True）...")
                    # 发送空的结束包（NEG_SEQUENCE 标记），告诉服务器音频结束
                    await self.ws_client.send_audio(b'\x00\x00', is_last=True)
                    self.logger.info("✅ [最后包已发送] is_last=True")
                    break
                
                segment_count += 1
                total_bytes += len(audio_data)
                segment_start = time.time()
                
                # 发送音频数据
                await self.ws_client.send_audio(audio_data, is_last=False)
                
                segment_elapsed = (time.time() - segment_start) * 1000
                
                if segment_count % 5 == 0:  # 每5个segment记录一次
                    self.logger.info(f"📤 [实时发送] 第 {segment_count} 段, 大小={len(audio_data)}字节, 耗时={segment_elapsed:.2f}ms")
            
            total_send_elapsed = (time.time() - send_start) * 1000
            self.logger.info(f"✅ [发送完成] 共发送 {segment_count} 段, {total_bytes} 字节, 总耗时: {total_send_elapsed:.2f}ms")
            
        except Exception as e:
            self.logger.error(f"❌ [发送循环错误] {e}", exc_info=True)
            self.error_message = f"发送音频失败: {str(e)}"
            self.is_recording = False
    
    def _extract_text(self, payload_msg) -> str:
        """从 v2 协议响应 payload 中提取识别文本（result 可能是 list 或 dict）"""
        if not payload_msg:
            return ""
        result = payload_msg.get('result')
        if isinstance(result, list):
            return result[0].get('text', '') if result else ""
        if isinstance(result, dict):
            return result.get('text', '')
        return ""

    async def _receiver_loop(self):
        """接收循环：接收 ASR 响应"""
        self.logger.info("📥 [接收循环] 启动...")
        response_count = 0
        
        try:
            async for response in self.ws_client.recv_messages():
                response_count += 1
                
                if response.code != 0:
                    message = (response.payload_msg or {}).get('message', '')
                    self.logger.error(f"❌ [识别错误] code={response.code}, msg={response.payload_msg}")
                    if response.code == 1013:
                        # 火山引擎 1013：VAD 未检测到有效语音（常见原因：麦克风权限/静音）
                        self.error_message = "未检测到有效语音，请检查麦克风权限和音量（系统设置 → 隐私与安全性 → 麦克风）"
                    else:
                        self.error_message = f"识别错误 (code={response.code})" + (f": {message}" if message else "")
                    self.is_recording = False
                    break
                
                # 服务端按块返回结果：结束块已发送且收到的响应数达到发送块数时，
                # 该响应即为最终结果（响应可能滞后于发送，不能以 is_last 为准）
                # Soniox adapter emits one explicit final response after its
                # worker has drained the audio stream.  Volcengine keeps the
                # original chunk-count based completion check below.
                if self.provider == 'soniox' and response.is_last_package:
                    self.result_text = self._extract_text(response.payload_msg)
                    if response.code != 0:
                        self.error_message = (response.payload_msg or {}).get('message', 'Soniox 识别失败')
                    elif self.result_text:
                        self.logger.info(f"✅ [Soniox识别成功] 文本: \"{self.result_text}\"")
                    else:
                        self.error_message = "未检测到有效语音内容"
                    break

                if self.ws_client.finished and response_count >= self.ws_client.chunks_sent:
                    self.result_text = self._extract_text(response.payload_msg)
                    
                    if self.result_text:
                        self.logger.info(f"✅ [识别成功] 文本: \"{self.result_text}\"")
                    else:
                        self.logger.warning("⚠️ [无识别结果] 未检测到有效语音")
                        self.error_message = "未检测到有效语音内容"
                    
                    break
                
                # 中间结果（可选）
                if response.payload_msg:
                    partial_text = self._extract_text(response.payload_msg)
                    if partial_text:
                        self.partial_text = partial_text
                    if partial_text and response_count % 5 == 0:  # 每5个响应记录一次
                        self.logger.debug(f"📝 [部分结果] \"{partial_text}\"")
            
            self.logger.info(f"🏁 [接收完成] 共接收 {response_count} 个响应")
            
        except Exception as e:
            self.logger.error(f"❌ [接收循环错误] {e}", exc_info=True)
            self.error_message = f"接收响应失败: {str(e)}"
            self.is_recording = False
    
    def _save_wav_file(self) -> str:
        """保存录音为WAV文件"""
        try:
            if not self.audio_buffer:
                self.logger.warning("⚠️ [保存录音] 音频缓冲区为空，无法保存")
                return None
            
            # 创建保存目录
            save_dir = Path(__file__).parent.parent.parent / "data" / "voices"
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名（使用时间戳）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"voice_{timestamp}.wav"
            filepath = save_dir / filename
            
            # 合并所有音频数据
            audio_data = b''.join(self.audio_buffer)
            
            # 保存为WAV文件
            with wave.open(str(filepath), 'wb') as wf:
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(2)  # 16bit = 2 bytes
                wf.setframerate(self.RATE)
                wf.writeframes(audio_data)
            
            file_size = len(audio_data)
            duration_sec = len(audio_data) / (self.RATE * self.CHANNELS * 2)
            self.logger.info(f"💾 [保存录音] 文件: {filename}, 大小: {file_size}字节, 时长: {duration_sec:.2f}秒")
            
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"❌ [保存录音失败] {e}", exc_info=True)
            return None
    
    async def _close_asr_connection(self):
        try:
            await asyncio.wait_for(self.ws_client.__aexit__(None, None, None), timeout=2.0)
        except asyncio.TimeoutError:
            self.logger.warning('ASR 连接关闭超时，保留已识别文字')
        except Exception as error:
            self.logger.warning('ASR 连接清理失败: %s', error)

    async def stop_streaming(self, finalize=True):
        """停止实时流式识别"""
        stop_start = time.time()
        stop_deadline_start = time.monotonic()
        self.logger.info("=" * 80)
        self.logger.info("🛑 [停止识别] 开始停止...")
        self.logger.info("=" * 80)
        
        try:
            # Cancelling keeps the currently recognized draft; submitting waits
            # for final ASR tokens. Neither path leaves a capture worker running.
            self.is_recording = False
            if not finalize:
                self.result_text = self.result_text or self.partial_text
                asr_task = getattr(self, '_task', None)
                if asr_task and asr_task is not asyncio.current_task() and not asr_task.done():
                    asr_task.cancel()
                    await asyncio.wait({asr_task}, timeout=1)
            await asyncio.gather(*(asyncio.to_thread(thread.join, 2.0) for thread in self._capture_threads))
            # Do not rely solely on a device worker to signal EOF: an unplugged
            # or blocked device may never reach its normal exit path.
            self._finish_capture()
            self.logger.info('停止采集阶段耗时: %.2fms', (time.time() - stop_start) * 1000)
            streams = list(self._input_streams.values()) or ([self.stream] if self.stream else [])
            def close_inputs():
                for stream in streams:
                    try:
                        stream.stop_stream()
                    finally:
                        stream.close()
                if self.p:
                    self.p.terminate()
            await asyncio.wait_for(asyncio.to_thread(close_inputs), timeout=3)
            self.logger.info("✅ [录音已停止]")

            # 2. 保存录音文件
            self.logger.info("💾 [保存录音] 正在保存录音文件...")
            saved_file = await asyncio.to_thread(self._save_wav_file)
            if saved_file:
                self.saved_audio_file = saved_file
                self.logger.info(f"✅ [录音已保存] 路径: {saved_file}")
            
            if finalize:
                # The ASR task already awaits both sender and receiver. Queue
                # emptiness is not delivery confirmation, and polling result_text
                # after task completion only adds a redundant three-second wait.
                self.logger.info("⏳ [等待结果] 等待 ASR 返回最终结果...")
                result_start = time.time()
                asr_task = getattr(self, '_task', None)
                if asr_task and asr_task is not asyncio.current_task():
                    try:
                        await asyncio.wait_for(asyncio.shield(asr_task), timeout=max(0.0, 1.0 - (time.monotonic() - stop_deadline_start)))
                    except asyncio.TimeoutError:
                        self.logger.warning("最终识别等待达到1秒，立即采用当前识别文字")
                        asr_task.cancel()
                    except asyncio.CancelledError:
                        if not asr_task.cancelled():
                            raise
                    except Exception as task_error:
                        self.logger.warning(f"⚠️ [等待结果] ASR 任务结束异常: {task_error}")
                self.logger.info("✅ [结果获取] 耗时: %.2fms", (time.time() - result_start) * 1000)

            # 如果服务端只返回非最终 token，使用最新的实时假设，避免
            # 因网络关闭时序导致空结果。
            if not self.result_text and self.partial_text and not self.error_message:
                self.result_text = self.partial_text
            
            # Final text is fixed now. The WebSocket close handshake must not
            # delay returning it to the composer / language model.
            if self.ws_client:
                if finalize:
                    cleanup = asyncio.create_task(self._close_asr_connection())
                    _connection_cleanup_tasks.add(cleanup)
                    cleanup.add_done_callback(_connection_cleanup_tasks.discard)
                else:
                    await self._close_asr_connection()

            total_stop_elapsed = (time.time() - stop_start) * 1000
            self.logger.info(f"🏁 [停止完成] 总耗时: {total_stop_elapsed:.2f}ms")
            self.logger.info("=" * 80)
            
            self.logger.info("录音音量诊断: device=%s, raw_peak=%s, processed_peak=%s",
                             self.input_device_name, self.raw_peak, self.processed_peak)
            # Distinguish silent capture from an ASR/network failure.
            if self.audio_buffer and self.raw_peak == 0:
                return None, (f"麦克风「{self.input_device_name}」采集到的声音全为静音。"
                              "请检查系统声音输入设备、输入音量，以及启动后端的应用的麦克风权限；"
                              "若 MacBook 合盖，请开盖或使用外接麦克风。")

            # 返回结果
            if self.result_text:
                # 如果是自动停止，在结果中添加提示
                if self.auto_stopped:
                    self.logger.info(f"⏰ [自动停止提示] 录音因达到时长上限而自动停止")
                return self.result_text, None
            else:
                error_msg = self.error_message or "识别失败，未获取到结果"
                # 如果是自动停止但没有识别结果，添加特殊提示
                if self.auto_stopped:
                    error_msg = f"录音已达到最大时长({self.max_duration_seconds/60:.1f}分钟)，但{error_msg}"
                return None, error_msg
            
        except Exception as e:
            total_elapsed = (time.time() - stop_start) * 1000
            self.logger.error(f"❌ [停止失败] 耗时: {total_elapsed:.2f}ms - {e}", exc_info=True)
            return None, f"停止识别失败: {str(e)}"
