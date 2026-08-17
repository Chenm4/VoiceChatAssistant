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
from backend.services.volcengine_streaming import VolcengineStreamingClient
from config import AUDIO_CONFIG, VOLCENGINE_CONFIG


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
        self.error_message: Optional[str] = None
        self.ws_client: Optional[VolcengineStreamingClient] = None
        self.stream: Optional[pyaudio.Stream] = None
        self.p: Optional[pyaudio.PyAudio] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.connection_ready: bool = False
        self.audio_buffer: list = []
        self.preloaded: bool = preload
        self.recording_start_time: Optional[float] = None  # 录音开始时间
        self.max_duration_seconds: int = AUDIO_CONFIG.get('max_duration_minutes', 5) * 60  # 最大录音时长（秒）
        self.auto_stopped: bool = False  # 是否因超时自动停止
        
        # 音频参数
        self.CHUNK: int = AUDIO_CONFIG['chunk']
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS: int = AUDIO_CONFIG['channels']
        self.RATE: int = AUDIO_CONFIG['rate']
        
        # WebSocket 参数（火山引擎 v2/asr 协议）
        self.url: str = VOLCENGINE_CONFIG.get('ws_url', 'wss://openspeech.bytedance.com/api/v2/asr')
        self.segment_duration: int = VOLCENGINE_CONFIG.get('segment_duration', 200)
        
        # 计算每个音频包的大小（字节数）
        # segment_duration (200ms) -> 每包需要多少帧
        self.frames_per_segment: int = int(self.RATE * self.segment_duration / 1000)
        self.bytes_per_segment: int = self.frames_per_segment * self.CHANNELS * 2
        
        # 预热 PyAudio（只创建实例，不打开设备）
        if preload:
            try:
                self.p = pyaudio.PyAudio()
                self.logger.info("🔥 [预热] PyAudio 实例已创建（未打开麦克风）")
            except Exception as e:
                self.logger.warning(f"⚠️ [预热失败] PyAudio 预热失败: {e}")
                self.p = None
        
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
    
    async def start_streaming(self):
        """
        开始实时流式识别（优化版：先录音，后建连 + 预热支持）
        1. 立即启动录音线程（缓冲音频）
        2. 并行建立 WebSocket 连接
        3. 发送配置请求
        4. 标记连接就绪，开始发送缓冲的音频
        """
        start_time = time.time()
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
            self.recording_start_time = time.time()  # 记录开始时间
            self._start_audio_capture()
            
            record_elapsed = (time.time() - record_start) * 1000
            self.logger.info(f"✅ [录音已启动] 耗时: {record_elapsed:.2f}ms (音频正在缓冲)")
            
            # 2. 建立 WebSocket 连接（录音已经在进行中）
            connect_start = time.time()
            self.logger.info("🔗 [建立连接] 正在连接到 ASR 服务（录音已开始）...")
            
            self.ws_client = VolcengineStreamingClient(
                appid=VOLCENGINE_CONFIG['appid'],
                token=VOLCENGINE_CONFIG['token'],
                cluster=VOLCENGINE_CONFIG['cluster'],
                ws_url=self.url,
                segment_duration=self.segment_duration
            )
            self.logger.info(f"📝 [创建客户端] URL={self.url}, segment_duration={self.segment_duration}ms")
            
            await self.ws_client.__aenter__()  # 创建 session
            self.logger.info("✅ [Session创建] aiohttp session 已创建")
            
            await self.ws_client.create_connection()
            self.logger.info(f"✅ [WebSocket连接] 连接对象: {self.ws_client.ws}")
            
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
            raise
    
    def _start_audio_capture(self):
        """启动音频捕获线程（打开麦克风）"""
        try:
            # 如果没有预热的PyAudio实例，现在创建
            if not self.p:
                self.p = pyaudio.PyAudio()
                self.logger.info("🎤 [音频设备] 创建 PyAudio 实例")
            
            # 打开音频流（真正打开麦克风）
            self.stream = self.p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            self.logger.info("🎤 [音频设备] 麦克风已打开")
            
            def capture_audio():
                buffer = b''
                chunk_count = 0
                
                self.logger.info("🎙️ [音频捕获] 开始捕获音频数据...")
                self.logger.info(f"⏱️ [时长限制] 最大录音时长: {self.max_duration_seconds}秒 ({self.max_duration_seconds/60:.1f}分钟)")
                
                while self.is_recording:
                    try:
                        # 检查是否超过最大录音时长
                        if self.recording_start_time:
                            elapsed_time = time.time() - self.recording_start_time
                            if elapsed_time >= self.max_duration_seconds:
                                self.logger.warning(f"⏰ [超时自动停止] 录音时长已达到上限 {self.max_duration_seconds}秒，自动停止")
                                self.auto_stopped = True
                                self.is_recording = False
                                break
                        
                        # 读取音频数据
                        data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                        buffer += data
                        chunk_count += 1
                        
                        # 保存到音频缓冲区（用于生成WAV文件）
                        self.audio_buffer.append(data)
                        
                        # 当累积到一个完整的segment时，放入队列
                        while len(buffer) >= self.bytes_per_segment:
                            segment = buffer[:self.bytes_per_segment]
                            buffer = buffer[self.bytes_per_segment:]
                            
                            # 使用线程安全的方式将数据放入异步队列
                            # 使用保存的事件循环引用
                            asyncio.run_coroutine_threadsafe(
                                self.audio_queue.put(segment),
                                self.loop  # 使用保存的事件循环引用
                            )
                            
                            if chunk_count % 10 == 0:  # 每10个chunk记录一次
                                self.logger.debug(f"📥 [音频缓冲] 已捕获 {chunk_count} 个chunk, 队列大小: {self.audio_queue.qsize()}")
                    
                    except Exception as e:
                        self.logger.error(f"❌ [音频捕获错误] {e}")
                        break
                
                # 录音结束，发送剩余数据
                if buffer:
                    self.logger.info(f"📦 [最后数据] 发送剩余 {len(buffer)} 字节")
                    asyncio.run_coroutine_threadsafe(
                        self.audio_queue.put(buffer),
                        self.loop  # 使用保存的事件循环引用
                    )
                
                # 发送结束标记
                asyncio.run_coroutine_threadsafe(
                    self.audio_queue.put(None),
                    self.loop  # 使用保存的事件循环引用
                )
                
                self.logger.info(f"🏁 [音频捕获] 音频捕获线程结束，共捕获 {len(self.audio_buffer)} 个数据块")
            
            self.capture_thread = threading.Thread(target=capture_audio, daemon=True)
            self.capture_thread.start()
            
        except Exception as e:
            self.logger.error(f"❌ [音频捕获启动失败] {e}", exc_info=True)
            raise
    
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
                    break
                
                # 服务端按块返回结果：结束块已发送且收到的响应数达到发送块数时，
                # 该响应即为最终结果（响应可能滞后于发送，不能以 is_last 为准）
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
                    if partial_text and response_count % 5 == 0:  # 每5个响应记录一次
                        self.logger.debug(f"📝 [部分结果] \"{partial_text}\"")
            
            self.logger.info(f"🏁 [接收完成] 共接收 {response_count} 个响应")
            
        except Exception as e:
            self.logger.error(f"❌ [接收循环错误] {e}", exc_info=True)
            self.error_message = f"接收响应失败: {str(e)}"
    
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
    
    async def stop_streaming(self):
        """停止实时流式识别"""
        stop_start = time.time()
        self.logger.info("=" * 80)
        self.logger.info("🛑 [停止识别] 开始停止...")
        self.logger.info("=" * 80)
        
        try:
            # 1. 停止录音
            self.logger.info("🎤 [停止录音] 关闭音频流...")
            self.is_recording = False
            
            if hasattr(self, 'capture_thread'):
                self.capture_thread.join(timeout=2.0)
            
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.p:
                self.p.terminate()
            
            self.logger.info("✅ [录音已停止]")
            
            # 2. 保存录音文件
            self.logger.info("💾 [保存录音] 正在保存录音文件...")
            saved_file = self._save_wav_file()
            if saved_file:
                self.logger.info(f"✅ [录音已保存] 路径: {saved_file}")
            
            # 3. 等待队列处理完成（最多等待3秒）
            self.logger.info("⏳ [等待队列] 等待音频数据发送完成...")
            wait_start = time.time()
            
            for _ in range(30):  # 最多等待3秒
                if self.audio_queue.empty():
                    break
                await asyncio.sleep(0.1)
            
            wait_elapsed = (time.time() - wait_start) * 1000
            self.logger.info(f"✅ [队列清空] 耗时: {wait_elapsed:.2f}ms")
            
            # 4. 等待识别结果（最多等待5秒）
            self.logger.info("⏳ [等待结果] 等待 ASR 返回最终结果...")
            result_start = time.time()
            
            for _ in range(50):  # 最多等待5秒
                if self.result_text or self.error_message:
                    break
                await asyncio.sleep(0.1)
            
            result_elapsed = (time.time() - result_start) * 1000
            self.logger.info(f"✅ [结果获取] 耗时: {result_elapsed:.2f}ms")
            
            # 5. 关闭 WebSocket 连接
            self.logger.info("🔌 [关闭连接] 关闭 WebSocket...")
            if self.ws_client:
                await self.ws_client.__aexit__(None, None, None)
            
            total_stop_elapsed = (time.time() - stop_start) * 1000
            self.logger.info(f"🏁 [停止完成] 总耗时: {total_stop_elapsed:.2f}ms")
            self.logger.info("=" * 80)
            
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
