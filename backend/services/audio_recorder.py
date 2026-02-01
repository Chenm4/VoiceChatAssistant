"""
音频录制服务

提供音频录制功能，支持实时录音和文件保存。
使用 PyAudio 进行音频采集，录音文件保存为 WAV 格式。
"""

import sys
import threading
import wave
from datetime import datetime
from pathlib import Path
from typing import Optional

import pyaudio

# 添加父目录到路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.utils.logger import get_asr_logger
from config import AUDIO_CONFIG


# 常量定义
VOICE_DIR = Path(__file__).parent.parent.parent / "data" / "voices"


class AudioRecorder:
    """
    音频录制器
    
    提供音频录制功能，支持实时录音和文件保存。
    使用 PyAudio 进行音频采集，录音文件自动保存为 WAV 格式。
    
    Attributes:
        is_recording: 是否正在录音
        frames: 音频帧缓冲区
        stream: PyAudio 音频流对象
        p: PyAudio 实例
        logger: 日志记录器
        
    Example:
        >>> recorder = AudioRecorder()
        >>> recorder.start()
        >>> # 录音中...
        >>> audio_path = recorder.stop()
        >>> print(f"录音已保存到: {audio_path}")
    """
    
    def __init__(self) -> None:
        """
        初始化音频录制器
        
        从配置文件读取音频参数（采样率、声道数等），
        并初始化录音状态。
        """
        self.is_recording: bool = False
        self.frames: list = []
        self.stream: Optional[pyaudio.Stream] = None
        self.p: Optional[pyaudio.PyAudio] = None
        self.logger = get_asr_logger()
        
        # 音频参数
        self.CHUNK: int = AUDIO_CONFIG['chunk']
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS: int = AUDIO_CONFIG['channels']
        self.RATE: int = AUDIO_CONFIG['rate']
        
        self.logger.info(
            f"初始化音频录制器: {self.CHANNELS}声道, "
            f"{self.RATE}Hz, {self.CHUNK}块大小"
        )
    
    def start(self) -> None:
        """
        开始录音
        
        初始化音频流并启动录音线程。
        如果已经在录音中，会记录警告并直接返回。
        
        录音数据会被实时缓冲到内存中，调用 stop() 时保存为文件。
        
        Raises:
            Exception: 录音启动失败时（如麦克风不可用、权限不足等）
        """
        if self.is_recording:
            self.logger.warning("录音已在进行中")
            return
        
        self.is_recording = True
        self.frames = []
        
        try:
            # 初始化 PyAudio
            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            
            self.logger.info("开始录音...")
            
            def record() -> None:
                """录音线程函数：持续读取音频数据"""
                while self.is_recording:
                    try:
                        data = self.stream.read(
                            self.CHUNK,
                            exception_on_overflow=False
                        )
                        self.frames.append(data)
                    except Exception as e:
                        self.logger.error(f"录音数据读取失败: {e}")
                        break
            
            # 启动录音线程
            self.record_thread = threading.Thread(target=record)
            self.record_thread.start()
            
        except Exception as e:
            self.logger.error(f"录音启动失败: {e}", exc_info=True)
            self.is_recording = False
            raise
    
    def stop(self) -> Optional[str]:
        """
        停止录音并保存文件
        
        停止录音线程，关闭音频流，并将录音数据保存为 WAV 文件。
        文件名使用时间戳自动生成，保存在 data/voices/ 目录。
        
        Returns:
            Optional[str]: 录音文件路径，如果没有录到数据则返回 None
            
        Example:
            >>> recorder.start()
            >>> time.sleep(5)  # 录音 5 秒
            >>> audio_path = recorder.stop()
            >>> print(f"录音文件: {audio_path}")
        """
        if not self.is_recording:
            self.logger.warning("没有正在进行的录音")
            return None
        
        # 停止录音标志
        self.is_recording = False
        
        # 等待录音线程结束
        if hasattr(self, 'record_thread'):
            self.record_thread.join(timeout=2.0)
        
        # 关闭音频流
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        # 获取采样宽度并关闭 PyAudio
        sample_width = 0
        if self.p:
            sample_width = self.p.get_sample_size(self.FORMAT)
            self.p.terminate()
        
        # 检查是否有录音数据
        if not self.frames:
            self.logger.warning("没有录到音频数据")
            return None
        
        # 创建保存目录
        VOICE_DIR.mkdir(parents=True, exist_ok=True)
        
        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        audio_filename = f"voice_{timestamp}.wav"
        audio_path = VOICE_DIR / audio_filename
        
        # 保存音频文件
        with wave.open(str(audio_path), 'wb') as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(sample_width)
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(self.frames))
        
        # 计算音频信息
        duration = len(self.frames) * self.CHUNK / self.RATE
        file_size = audio_path.stat().st_size
        
        self.logger.info(
            f"录音完成: 文件={audio_path}, "
            f"时长={duration:.2f}秒, 大小={file_size}字节"
        )
        
        return str(audio_path)
