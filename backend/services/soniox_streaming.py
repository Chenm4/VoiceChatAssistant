"""Soniox realtime STT adapter using the documented WebSocket protocol."""

import json
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, Optional

import websockets


DEFAULT_WS_URL = "wss://stt-rt.jp.soniox.com/transcribe-websocket"


@dataclass
class SonioxStreamingResponse:
    code: int
    payload_msg: Optional[Dict]
    is_last_package: bool = False


class SonioxStreamingClient:
    """Async client with the same small surface as the Volcengine adapter."""

    def __init__(self, api_key: str, ws_url: str = DEFAULT_WS_URL,
                 model: str = "stt-rt-v5", sample_rate: int = 16000,
                 num_channels: int = 1, language: str = "zh",
                 context: Optional[Dict[str, Any]] = None) -> None:
        if not api_key:
            raise ValueError("Soniox API key is empty; set SONIOX_API_KEY or config.py")
        self.api_key = api_key
        self.ws_url = ws_url
        self.model = model
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.language = language
        self.context = context
        self.ws = None
        self.chunks_sent = 0
        self.finished = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.ws:
            await self.ws.close()
            self.ws = None

    async def create_connection(self) -> None:
        self.ws = await websockets.connect(self.ws_url, max_size=1000000000)

    async def send_full_client_request(self) -> None:
        if not self.ws:
            raise RuntimeError("Soniox WebSocket is not connected")
        config = {
            "api_key": self.api_key,
            "model": self.model,
            "audio_format": "pcm_s16le",
            "sample_rate": self.sample_rate,
            "num_channels": self.num_channels,
            "language_hints": [self.language] if self.language else [],
            "enable_endpoint_detection": True,
        }
        if self.context:
            config["context"] = self.context
        await self.ws.send(json.dumps(config))

    async def send_audio(self, data: bytes, is_last: bool = False) -> None:
        if not self.ws:
            raise RuntimeError("Soniox WebSocket is not connected")
        if is_last:
            # Soniox documents both empty binary and empty text frames as the
            # end marker. The Japan endpoint reliably finalizes on an empty
            # text frame; an empty binary frame can otherwise time out (408).
            await self.ws.send("")
        else:
            await self.ws.send(data)
            self.chunks_sent += 1

    async def recv_messages(self) -> AsyncGenerator[SonioxStreamingResponse, None]:
        if not self.ws:
            raise RuntimeError("Soniox WebSocket is not connected")

        final_tokens = []
        latest_non_final_tokens = []
        sent_final_response = False
        async for raw in self.ws:
            if isinstance(raw, bytes):
                try:
                    raw = raw.decode("utf-8")
                except UnicodeDecodeError:
                    continue
            try:
                event = json.loads(raw)
            except (TypeError, json.JSONDecodeError) as exc:
                yield SonioxStreamingResponse(-1, {"message": f"Soniox 响应不是合法 JSON: {exc}"}, True)
                break

            if event.get("error_code"):
                yield SonioxStreamingResponse(
                    int(event.get("error_code", -1)),
                    {
                        "message": event.get("error_message", "Soniox 识别失败"),
                        "error_type": event.get("error_type"),
                        "request_id": event.get("request_id"),
                        "more_info": event.get("more_info"),
                    },
                    True,
                )
                break

            tokens = event.get("tokens") or []
            final_tokens.extend(
                token.get("text", "")
                for token in tokens
                if token.get("is_final") and token.get("text") != "<end>"
            )
            non_final_text = "".join(
                token.get("text", "")
                for token in tokens
                if not token.get("is_final") and token.get("text") != "<end>"
            )
            current_non_final_tokens = [
                token.get("text", "")
                for token in tokens
                if not token.get("is_final") and token.get("text") != "<end>"
            ]
            if current_non_final_tokens:
                latest_non_final_tokens = current_non_final_tokens
            elif any(token.get("is_final") for token in tokens):
                # Once final tokens arrive, the previous provisional
                # hypothesis has been superseded and must not be appended to
                # the following empty ``finished`` response.
                latest_non_final_tokens = []
            finished = bool(event.get("finished"))
            self.finished = finished
            # A short stream can end with only a final empty response while
            # the last useful hypothesis is still non-final.  Preserve that
            # hypothesis as the final text rather than returning no result.
            text = (
                "".join(final_tokens) + "".join(latest_non_final_tokens)
                if finished
                else "".join(final_tokens) + non_final_text
            )
            yield SonioxStreamingResponse(
                0, {"result": [{"text": text}], "tokens": tokens}, finished
            )
            if finished:
                sent_final_response = True
                break

        # Some proxies close the socket immediately after the last JSON
        # response.  If the server omitted ``finished`` but sent hypotheses,
        # still expose a deterministic final response to the caller.
        if not sent_final_response:
            text = "".join(final_tokens) + "".join(latest_non_final_tokens)
            yield SonioxStreamingResponse(
                0, {"result": [{"text": text}], "tokens": []}, True
            )
