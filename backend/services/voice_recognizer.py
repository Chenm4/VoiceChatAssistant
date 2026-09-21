"""
语音识别服务

提供可切换的语音识别功能。
默认使用 Soniox，失败时自动切换到配置的备用 ASR。

支持的识别器：
1. Soniox ASR（默认）
2. 火山引擎或字节跳动 ASR（可选备用）
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Tuple, Optional

# 添加父目录到路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.utils.asr_demo import AsrWsClient as VolcengineAsrClient, AudioType
from backend.utils.logger import get_asr_logger
from backend.utils.sauc_client import AsrWsClient as BytedanceAsrClient
import websockets
from config import ASR_CONFIG, BYTEDANCE_ASR_CONFIG, SONIOX_CONFIG, VOLCENGINE_CONFIG


class VoiceRecognizer:
    """
    语音识别服务
    
    使用可配置的主/备用识别器策略提供高可用的语音识别功能。
    默认使用 Soniox，失败时自动切换到配置的备用 ASR。
    
    Attributes:
        bd_app_key: 字节跳动 ASR 应用密钥
        bd_access_key: 字节跳动 ASR 访问密钥
        bd_url: 字节跳动 ASR WebSocket URL
        bd_segment_duration: 音频分段时长（毫秒）
        ve_appid: 火山引擎应用 ID
        ve_token: 火山引擎访问令牌
        ve_cluster: 火山引擎集群标识
        logger: 日志记录器
        
    Example:
        >>> recognizer = VoiceRecognizer()
        >>> text, error = await recognizer.recognize_file("audio.wav")
        >>> if text:
        ...     print(f"识别结果: {text}")
    """
    
    def __init__(self) -> None:
        """
        初始化语音识别服务
        
        从配置文件加载各 ASR 提供方的 API 配置。
        """
        self.logger = get_asr_logger()
        self.provider: str = ASR_CONFIG.get('provider', 'soniox').lower()
        self.fallback_provider: str = ASR_CONFIG.get('fallback_provider', 'volcengine').lower()
        
        # 字节跳动配置（主要）
        self.bd_app_key: str = BYTEDANCE_ASR_CONFIG['app_key']
        self.bd_access_key: str = BYTEDANCE_ASR_CONFIG['access_key']
        self.bd_url: str = BYTEDANCE_ASR_CONFIG['url']
        self.bd_segment_duration: int = BYTEDANCE_ASR_CONFIG.get('segment_duration', 200)
        
        # 火山引擎配置（备用）
        self.ve_appid: str = VOLCENGINE_CONFIG['appid']
        self.ve_token: str = VOLCENGINE_CONFIG['token']
        self.ve_cluster: str = VOLCENGINE_CONFIG['cluster']
        
        self.logger.info("初始化语音识别服务:")
        self.logger.info(f"  默认: {self.provider} | 备用: {self.fallback_provider}")
        self.logger.info(
            f"  Soniox (api_key={'SET' if SONIOX_CONFIG.get('api_key') else 'EMPTY'}, "
            f"host={SONIOX_CONFIG.get('api_host')}, model={SONIOX_CONFIG.get('model')})"
        )
        self.logger.info(
            f"  主要: 字节跳动 ASR "
            f"(app_key={'SET' if self.bd_app_key else 'EMPTY'}, "
            f"access_key={'SET' if self.bd_access_key else 'EMPTY'})"
        )
        self.logger.info(
            f"  备用: 火山引擎 ASR "
            f"(appid={'SET' if self.ve_appid else 'EMPTY'}, "
            f"token={'SET' if self.ve_token else 'EMPTY'}, "
            f"cluster={self.ve_cluster})"
        )
    
    async def recognize_with_bytedance(self, audio_file: str) -> Tuple[Optional[str], Optional[str]]:
        """
        使用字节跳动 ASR 识别音频文件
        
        Args:
            audio_file: 音频文件路径
            
        Returns:
            Tuple[Optional[str], Optional[str]]: (识别结果文本, 错误信息)
                - 成功时返回 (文本, None)
                - 失败时返回 (None, 错误信息)
                
        Example:
            >>> text, error = await recognizer.recognize_with_bytedance("test.wav")
            >>> if text:
            ...     print(f"识别成功: {text}")
        """
        self.logger.info(f"🎯 使用字节跳动 ASR 识别: {audio_file}")
        
        try:
            async with BytedanceAsrClient(
                url=self.bd_url,
                segment_duration=self.bd_segment_duration
            ) as client:
                final_text = ""
                async for response in client.execute(audio_file):
                    self.logger.debug(f"收到响应: code={response.code}, is_last={response.is_last_package}")
                    
                    if response.code == 0:  # 成功
                        if response.is_last_package and response.payload_msg:
                            # 最后一个包包含完整识别结果
                            result = response.payload_msg.get('result', {})
                            final_text = result.get('text', '')
                            
                            if final_text:
                                self.logger.info(f"✅ 字节跳动识别成功: {final_text}")
                                return final_text, None
                            else:
                                error_msg = "识别成功但没有检测到有效语音内容"
                                self.logger.warning(f"⚠️ {error_msg}")
                                return None, error_msg
                    else:
                        error_msg = f"字节跳动 ASR 错误 (code={response.code})"
                        self.logger.error(f"❌ {error_msg}")
                        return None, error_msg
                
                # 如果循环结束但没有获取到结果
                if not final_text:
                    error_msg = "未收到有效的识别结果"
                    self.logger.warning(f"⚠️ {error_msg}")
                    return None, error_msg
                    
        except Exception as e:
            error_msg = f"字节跳动识别异常: {str(e)}"
            self.logger.error(f"❌ {error_msg}", exc_info=True)
            return None, error_msg
    
    async def recognize_with_volcengine(self, audio_file: str) -> Tuple[Optional[str], Optional[str]]:
        """
        使用火山引擎 ASR 识别音频文件（备用）
        
        Args:
            audio_file: 音频文件路径
            
        Returns:
            Tuple[Optional[str], Optional[str]]: (识别结果文本, 错误信息)
                - 成功时返回 (文本, None)
                - 失败时返回 (None, 错误信息)
        """
        self.logger.info(f"🔄 使用火山引擎 ASR 识别（备用）: {audio_file}")
        
        try:
            client = VolcengineAsrClient(
                audio_path=audio_file,
                cluster=self.ve_cluster,
                appid=self.ve_appid,
                token=self.ve_token,
                format='wav',
                audio_type=AudioType.LOCAL
            )
            
            result = await client.execute()
            
            self.logger.debug(f"火山引擎响应: {result}")
            
            if 'payload_msg' in result:
                payload = result['payload_msg']
                code = payload.get('code')
                message = payload.get('message', '')
                
                if code == 1000:  # 成功
                    if 'result' in payload and len(payload['result']) > 0:
                        text = payload['result'][0].get('text', '')
                        self.logger.info(f"✅ 火山引擎识别成功: {text}")
                        return text, None
                    else:
                        error_msg = "识别成功但没有检测到有效语音内容"
                        self.logger.warning(f"⚠️ {error_msg}")
                        return None, error_msg
                elif code == 1013:  # 没有找到有效语音
                    error_msg = f"没有找到有效语音 - {message}"
                    self.logger.warning(f"⚠️ {error_msg}")
                    return None, error_msg
                elif code == 403:  # 权限错误
                    error_msg = f"火山引擎权限错误 (403): {message}\n可能原因：Token过期、服务欠费或权限未授权"
                    self.logger.error(f"❌ {error_msg}")
                    return None, error_msg
                else:
                    error_msg = f"识别失败 (错误码: {code}): {message}"
                    self.logger.error(f"❌ {error_msg}")
                    return None, error_msg
            else:
                error_msg = "API响应格式错误：未找到 payload_msg"
                self.logger.error(f"❌ {error_msg}")
                return None, error_msg
                
        except Exception as e:
            error_msg = f"火山引擎识别异常: {str(e)}"
            self.logger.error(f"❌ {error_msg}", exc_info=True)
            return None, error_msg
    
    async def recognize_with_soniox(self, audio_file: str) -> Tuple[Optional[str], Optional[str]]:
        """Recognize a WAV file through the Soniox Japan project endpoint."""
        self.logger.info(f"🎯 使用 Soniox ASR 识别: {audio_file}")
        if not SONIOX_CONFIG.get('api_key'):
            return None, "Soniox API Key 未设置，请设置 SONIOX_API_KEY"
        try:
            with open(audio_file, 'rb') as audio_file_handle:
                audio = audio_file_handle.read()
            ws_url = SONIOX_CONFIG.get('ws_url', 'wss://stt-rt.jp.soniox.com/transcribe-websocket')
            config = {
                'api_key': SONIOX_CONFIG['api_key'],
                'model': SONIOX_CONFIG.get('model', 'stt-rt-v5'),
                'audio_format': 'wav',
                'language_hints': [SONIOX_CONFIG.get('language', 'zh')],
                'enable_endpoint_detection': True,
            }
            if SONIOX_CONFIG.get('context'):
                config['context'] = SONIOX_CONFIG['context']
            final_tokens = []
            async with websockets.connect(ws_url, max_size=1000000000) as ws:
                await ws.send(json.dumps(config))
                await ws.send(audio)
                # The Japan endpoint finalizes reliably with an empty text
                # frame (an empty binary frame may remain pending until the
                # request timeout).
                await ws.send('')
                async for raw in ws:
                    if isinstance(raw, bytes):
                        raw = raw.decode('utf-8')
                    event = json.loads(raw)
                    if event.get('error_code'):
                        return None, event.get('error_message', 'Soniox 识别失败')
                    final_tokens.extend(
                        token.get('text', '')
                        for token in (event.get('tokens') or [])
                        if token.get('is_final') and token.get('text') != '<end>'
                    )
                    if event.get('finished'):
                        break
            text = ''.join(final_tokens)
            if text:
                self.logger.info(f"✅ Soniox 识别成功: {text}")
                return text, None
            return None, "Soniox 未检测到有效语音内容"
        except Exception as e:
            error_msg = f"Soniox 识别异常: {str(e)}"
            self.logger.error(f"❌ {error_msg}", exc_info=True)
            return None, error_msg

    async def recognize_file(self, audio_file: str) -> Tuple[Optional[str], Optional[str]]:
        """
        识别音频文件（智能切换策略）

        按 ``ASR_CONFIG`` 中的主识别器和备用识别器依次尝试。
        自动记录识别耗时和切换过程。
        
        Args:
            audio_file: 音频文件路径
            
        Returns:
            Tuple[Optional[str], Optional[str]]: (识别结果文本, 错误信息)
                - 任一识别器成功时返回 (文本, None)
                - 全部失败时返回 (None, 最后的错误信息)
                
        Example:
            >>> text, error = await recognizer.recognize_file("recording.wav")
            >>> if text:
            ...     print(f"识别成功: {text}")
            ... else:
            ...     print(f"识别失败: {error}")
        """
        import time
        total_start = time.time()
        
        self.logger.info("=" * 80)
        self.logger.info(f"🎬 [开始识别] 音频文件: {audio_file}")
        self.logger.info("=" * 80)
        
        methods = {
            'soniox': self.recognize_with_soniox,
            'volcengine': self.recognize_with_volcengine,
            'bytedance': self.recognize_with_bytedance,
        }
        providers = []
        for name in (self.provider, self.fallback_provider):
            if name in methods and name not in providers:
                providers.append(name)

        errors = []
        for name in providers:
            started = time.time()
            self.logger.info(f"🎯 尝试 {name} ASR...")
            text, error = await methods[name](audio_file)
            elapsed = (time.time() - started) * 1000
            if text:
                total_elapsed = (time.time() - total_start) * 1000
                self.logger.info(f"✅ {name} 识别成功 ({elapsed:.2f}ms，总计 {total_elapsed:.2f}ms)")
                return text, None
            errors.append(f"{name}: {error}")
            self.logger.warning(f"⚠️ {name} 失败 ({elapsed:.2f}ms): {error}")

        return None, "语音识别失败。" + "；".join(errors)
