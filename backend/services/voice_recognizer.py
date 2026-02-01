"""
语音识别服务

提供双识别器策略的语音识别功能。
优先使用字节跳动 ASR，失败时自动切换到火山引擎 ASR。

支持的识别器：
1. 字节跳动 ASR（主要）- 更准确
2. 火山引擎 ASR（备用）- 容错保障
"""

import asyncio
import sys
from pathlib import Path
from typing import Tuple, Optional

# 添加父目录到路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.utils.asr_demo import AsrWsClient as VolcengineAsrClient, AudioType
from backend.utils.logger import get_asr_logger
from backend.utils.sauc_client import AsrWsClient as BytedanceAsrClient
from config import BYTEDANCE_ASR_CONFIG, VOLCENGINE_CONFIG


class VoiceRecognizer:
    """
    语音识别服务
    
    使用双识别器策略提供高可用的语音识别功能。
    优先使用字节跳动 ASR，失败时自动切换到火山引擎 ASR。
    
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
        
        从配置文件加载字节跳动和火山引擎的 API 配置。
        """
        self.logger = get_asr_logger()
        
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
        self.logger.info(f"  主要: 字节跳动 ASR (app_key={self.bd_app_key})")
        self.logger.info(f"  备用: 火山引擎 ASR (appid={self.ve_appid}, cluster={self.ve_cluster})")
    
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
                    logger.debug(f"收到响应: code={response.code}, is_last={response.is_last_package}")
                    
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
    
    async def recognize_file(self, audio_file: str) -> Tuple[Optional[str], Optional[str]]:
        """
        识别音频文件（智能切换策略）
        
        优先使用字节跳动 ASR，失败时自动切换到火山引擎 ASR。
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
        
        # 1. 优先尝试字节跳动 ASR
        bd_start = time.time()
        self.logger.info("🎯 [方案A] 尝试字节跳动 ASR...")
        
        text, error = await self.recognize_with_bytedance(audio_file)
        
        bd_elapsed = (time.time() - bd_start) * 1000
        
        if text:
            total_elapsed = (time.time() - total_start) * 1000
            self.logger.info("✅ [成功] 字节跳动 ASR 识别成功")
            self.logger.info(f"📈 [耗时统计] 字节跳动: {bd_elapsed:.2f}ms | 总计: {total_elapsed:.2f}ms")
            self.logger.info("=" * 80)
            return text, None
        
        # 2. 字节跳动失败，尝试火山引擎 ASR
        self.logger.warning(f"⚠️ [失败] 字节跳动 ASR 失败 (耗时: {bd_elapsed:.2f}ms): {error}")
        self.logger.info("🔄 [切换] 切换到火山引擎 ASR（备用方案）")
        
        ve_start = time.time()
        self.logger.info("🎯 [方案B] 尝试火山引擎 ASR...")
        
        text, error = await self.recognize_with_volcengine(audio_file)
        
        ve_elapsed = (time.time() - ve_start) * 1000
        
        if text:
            total_elapsed = (time.time() - total_start) * 1000
            self.logger.info("✅ [成功] 火山引擎 ASR 识别成功")
            self.logger.info(
                f"📈 [耗时统计] 字节跳动: {bd_elapsed:.2f}ms | "
                f"火山引擎: {ve_elapsed:.2f}ms | 总计: {total_elapsed:.2f}ms"
            )
            self.logger.info("=" * 80)
            return text, None
        
        # 3. 两个都失败
        total_elapsed = (time.time() - total_start) * 1000
        self.logger.error("❌ [全部失败] 所有识别器均失败")
        self.logger.error(
            f"📈 [耗时统计] 字节跳动: {bd_elapsed:.2f}ms | "
            f"火山引擎: {ve_elapsed:.2f}ms | 总计: {total_elapsed:.2f}ms"
        )
        self.logger.info("=" * 80)
        
        final_error = f"语音识别失败。字节跳动和火山引擎识别器均不可用。最后错误: {error}"
        return None, final_error
