"""
火山引擎实时流式语音识别客户端

使用火山引擎 ASR v2 协议（wss://openspeech.bytedance.com/api/v2/asr），
认证方式为 Authorization: Bearer; {token}，凭据为 appid + token + cluster。

协议说明：
- full client request：携带 app/cluster/token 的配置请求
- audio-only request：逐段发送 PCM 音频（gzip 压缩），最后一段带 NEG_SEQUENCE 标记
- 服务端逐段返回识别结果（增量），发送最后一段后返回最终结果
"""

import asyncio
import gzip
import json
import uuid
from typing import AsyncGenerator, Dict, Optional

import websockets

from backend.utils.logger import get_asr_logger

logger = get_asr_logger()

DEFAULT_WS_URL = "wss://openspeech.bytedance.com/api/v2/asr"

# 协议常量
PROTOCOL_VERSION = 0b0001
CLIENT_FULL_REQUEST = 0b0001
CLIENT_AUDIO_ONLY_REQUEST = 0b0010
SERVER_FULL_RESPONSE = 0b1001
SERVER_ACK = 0b1011
SERVER_ERROR_RESPONSE = 0b1111
NO_SEQUENCE = 0b0000
NEG_SEQUENCE = 0b0010
JSON = 0b0001
GZIP = 0b0001

SUCCESS_CODE = 1000  # 火山引擎成功码


class VolcengineStreamingResponse:
    """流式识别响应"""

    def __init__(self, code: int, payload_msg: Optional[dict], is_last_package: bool = False):
        self.code = code  # 0 表示成功，非 0 为错误码
        self.payload_msg = payload_msg
        self.is_last_package = is_last_package


def _generate_header(message_type: int, flags: int = NO_SEQUENCE) -> bytes:
    """生成 v2 协议 4 字节头"""
    header = bytearray()
    header.append((PROTOCOL_VERSION << 4) | 1)  # header_size = 1
    header.append((message_type << 4) | flags)
    header.append((JSON << 4) | GZIP)
    header.append(0x00)
    return bytes(header)


def _parse_response(res: bytes) -> Dict:
    """解析 v2 协议响应"""
    header_size = res[0] & 0x0f
    message_type = res[1] >> 4
    compression = res[2] & 0x0f
    payload = res[header_size * 4:]
    result = {"message_type": message_type}

    if message_type == SERVER_FULL_RESPONSE:
        payload = payload[4:]  # 跳过 payload_size
    elif message_type == SERVER_ACK:
        result["seq"] = int.from_bytes(payload[:4], "big", signed=True)
        return result
    elif message_type == SERVER_ERROR_RESPONSE:
        result["code"] = int.from_bytes(payload[:4], "big")
        payload = payload[8:]

    if compression == GZIP and payload:
        payload = gzip.decompress(payload)
    if payload:
        result["payload"] = json.loads(payload.decode("utf-8"))
    return result


class VolcengineStreamingClient:
    """
    火山引擎实时流式识别客户端

    Attributes:
        appid: 应用 ID
        token: 访问令牌
        cluster: 集群标识
        ws_url: WebSocket 地址
        ws: WebSocket 连接
        chunks_sent: 已发送的音频块数
        finished: 是否已发送结束包
    """

    def __init__(self, appid: str, token: str, cluster: str,
                 ws_url: str = DEFAULT_WS_URL, segment_duration: int = 200) -> None:
        self.appid = appid
        self.token = token
        self.cluster = cluster
        self.ws_url = ws_url
        self.segment_duration = segment_duration
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.chunks_sent = 0  # 已发送的音频块数
        self.finished = False  # 是否已发送结束块

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.ws:
            await self.ws.close()

    async def create_connection(self) -> None:
        """建立 WebSocket 连接（Bearer token 认证）"""
        headers = {'Authorization': 'Bearer; {}'.format(self.token)}
        self.ws = await websockets.connect(
            self.ws_url,
            extra_headers=headers,
            max_size=1000000000
        )
        logger.info(f"✅ [火山引擎] 已连接: {self.ws_url}")

    async def send_full_client_request(self) -> None:
        """发送 full client request 并校验成功响应"""
        req = {
            'app': {
                'appid': self.appid,
                'cluster': self.cluster,
                'token': self.token,
            },
            'user': {
                'uid': 'streaming_asr'
            },
            'request': {
                'reqid': str(uuid.uuid4()),
                'nbest': 1,
                'workflow': 'audio_in,resample,partition,vad,fe,decode,itn,nlu_punctuate',
                'show_utterances': True,
                'result_type': 'full',
                'sequence': 1
            },
            'audio': {
                'format': 'pcm',
                'rate': 16000,
                'language': 'zh-CN',
                'bits': 16,
                'channel': 1,
                'codec': 'raw'
            }
        }
        payload = gzip.compress(json.dumps(req).encode('utf-8'))
        frame = bytearray(_generate_header(CLIENT_FULL_REQUEST))
        frame.extend(len(payload).to_bytes(4, 'big'))
        frame.extend(payload)
        await self.ws.send(bytes(frame))

        res = await self.ws.recv()
        parsed = _parse_response(res)
        if parsed["message_type"] == SERVER_ERROR_RESPONSE:
            raise ConnectionError(f"火山引擎认证失败: {parsed.get('payload')}")
        payload_msg = parsed.get("payload", {})
        if payload_msg.get("code") != SUCCESS_CODE:
            raise ConnectionError(f"火山引擎初始化失败 (code={payload_msg.get('code')}): {payload_msg.get('message', '')}")
        logger.info(f"✅ [火山引擎] 初始化请求成功: {payload_msg.get('message', '')}")

    async def send_audio(self, data: bytes, is_last: bool = False) -> None:
        """发送一段音频数据（gzip 压缩）"""
        flags = NEG_SEQUENCE if is_last else NO_SEQUENCE
        if is_last:
            self.finished = True
        payload = gzip.compress(data)
        frame = bytearray(_generate_header(CLIENT_AUDIO_ONLY_REQUEST, flags))
        frame.extend(len(payload).to_bytes(4, 'big'))
        frame.extend(payload)
        await self.ws.send(bytes(frame))
        self.chunks_sent += 1

    async def recv_messages(self) -> AsyncGenerator[VolcengineStreamingResponse, None]:
        """接收识别响应（跳过 ACK，返回识别结果或错误）"""
        try:
            async for msg in self.ws:
                # websockets 库迭代直接返回 bytes / str，而不是消息对象
                if isinstance(msg, str):
                    continue
                if not isinstance(msg, bytes):
                    continue

                parsed = _parse_response(msg)
                message_type = parsed["message_type"]

                if message_type == SERVER_ACK:
                    continue

                payload_msg = parsed.get("payload")

                if message_type == SERVER_ERROR_RESPONSE:
                    # 错误码：backend_code 为具体业务错误码
                    code = (payload_msg or {}).get("backend_code") or (payload_msg or {}).get("code", -1)
                    yield VolcengineStreamingResponse(code=code, payload_msg=payload_msg, is_last_package=self.finished)
                    continue

                # SERVER_FULL_RESPONSE
                code = SUCCESS_CODE
                if payload_msg and payload_msg.get("code") != SUCCESS_CODE:
                    code = payload_msg.get("code")
                    yield VolcengineStreamingResponse(code=code, payload_msg=payload_msg, is_last_package=self.finished)
                    continue

                yield VolcengineStreamingResponse(code=0, payload_msg=payload_msg, is_last_package=self.finished)
        except Exception as e:
            logger.error(f"❌ [火山引擎] 接收响应失败: {e}")
            raise
