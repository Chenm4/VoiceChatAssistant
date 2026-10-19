"""Browser-facing independent realtime voice bridge (JSON control + PCM frames)."""
import asyncio
import json
import wave
import shutil
import tempfile
from pathlib import Path
from contextlib import suppress
from typing import Literal, Optional
from urllib.parse import urlparse
from uuid import uuid4

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from backend.services import doubao_realtime as protocol
from backend.services.user_workspace import user_state, user_path
from backend.services.session_prompt import compose_session_system_prompt, render_session_user_prompt

router = APIRouter(prefix='/doubao-realtime', tags=['豆包实时语音'])


class StartOptions(BaseModel):
    type: Literal['start']
    model_config = ConfigDict(extra='forbid')
    session_id: str = Field(default='', max_length=128, pattern=r'^[A-Za-z0-9_-]*$')
    audio_file: Optional[str] = Field(default=None, min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=30000)
    system_role: str = Field(default='你是一个友好、自然、简洁的中文语音助手。', max_length=4000)


def session_instructions(session_id):
    session = user_state().session_storage.load_session(session_id)
    if session is None:
        raise ValueError('会话不存在')
    system = compose_session_system_prompt(session) or ''
    # Realtime accepts one instruction field: retain the shared user-template / scene
    # framing and explicitly bind its question placeholder to the live utterance.
    marker = '（本轮用户正在说的话）'
    user_rules = render_session_user_prompt(session, marker)
    return '\n\n'.join(part for part in (system, user_rules if user_rules != marker else '') if part)


@router.get('/config')
async def get_config():
    return {'configured': all(protocol.credentials()), 'model': protocol.MODEL, 'model_name': protocol.MODEL_NAME,
            'input_audio': {'format': 'pcm_s16le', 'sample_rate': 16000, 'channels': 1}}


def check_event(event):
    if event['type'] == 'error':
        raise RuntimeError('豆包服务返回错误，请检查参数、资源权限及额度')
    return event


async def receive_event(upstream, expected):
    async def wait():
        while True:
            event = check_event(protocol.decode_event(await upstream.recv()))
            if event['type'] == expected:
                return event
    return await asyncio.wait_for(wait(), 15)


async def finish_session(upstream):
    await upstream.send(protocol.encode_event('session.close'))
    async def wait():
        while True:
            event = protocol.decode_event(await upstream.recv())
            if event['type'] == 'session.closed':
                return
    await asyncio.wait_for(wait(), 3)


def load_recording(options):
    session = user_state().session_storage.load_session(options.session_id)
    if session is None or options.audio_file not in session.audio_files:
        raise ValueError('录音不属于当前会话')
    root = user_path('voices')
    path = (root / options.audio_file).resolve()
    if path.parent != root.resolve():
        raise ValueError('无效的录音路径')
    with wave.open(str(path), 'rb') as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
            raise ValueError('录音需要为单声道 16kHz PCM16')
        if not 0 < audio.getnframes() <= 16000 * 300:
            raise ValueError('录音长度必须在五分钟内')
        return audio.readframes(audio.getnframes())


async def text_input_pcm(text):
    """Local file-only synthesis adapts typed questions to the audio-only model."""
    say, convert = shutil.which('say'), shutil.which('afconvert')
    if not say or not convert:
        raise ValueError('当前服务器缺少本地文字转音频功能')
    async def run(*args, input_data=None):
        process = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            _, error = await asyncio.wait_for(process.communicate(input_data), 60)
            if process.returncode:
                raise ValueError('本地文字转音频失败')
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
    with tempfile.TemporaryDirectory(prefix='doubao-text-') as directory:
        source, output = str(Path(directory) / 'input.aiff'), str(Path(directory) / 'input.wav')
        await run(say, '-v', 'Tingting', '-r', '260', '-o', source, '-f', '-', input_data=text.encode('utf-8'))
        await run(convert, '-f', 'WAVE', '-d', 'LEI16@16000', '-c', '1', source, output)
        with wave.open(output, 'rb') as audio:
            if not 0 < audio.getnframes() <= 16000 * 300:
                raise ValueError('输入文字转换后的音频超过五分钟，请缩短问题')
            return audio.readframes(audio.getnframes())


async def bridge(browser, upstream, pcm):
    """Only entered after a completed recording is explicitly submitted.

    No browser audio or live microphone is accepted. Provider audio is discarded.
    """
    response_complete = asyncio.Event()

    async def receive():
        async for raw in upstream:
            event = check_event(protocol.decode_event(raw))
            kind = event['type']
            if kind == 'conversation.item.input_audio_transcription.started':
                response_complete.clear()
            if kind == 'response.output_text.delta':
                response_complete.clear()
            # The shared ASR's final text is already displayed; do not replace it
            # with provider fragments from replaying the same recording.
            if kind.startswith('conversation.item.input_audio_transcription.'):
                continue
            message = protocol.normalize_event(event)
            if message is not None and kind in ('response.output_text.delta', 'response.output_text.done'):
                await browser.send_json(message)
            if kind == 'response.output_text.done':
                response_complete.set()
            if kind == 'session.closed':
                raise RuntimeError('上游提前关闭')

    async def send():
        # The provider requires realtime pacing even when the source is a file.
        for offset in range(0, len(pcm), 640):
            await upstream.send(protocol.encode_audio(pcm[offset:offset + 640]))
            await asyncio.sleep(.02)
        await upstream.send(protocol.encode_event('input_audio_buffer.commit'))
        # Keep the session alive while waiting without reopening any microphone.
        await upstream.send(protocol.encode_event('input_audio_mute.commit'))
        await asyncio.wait_for(response_complete.wait(), 90)
        await browser.send_json({'type': 'complete'})

    async def watch_disconnect():
        while True:
            message = await browser.receive()
            if message['type'] == 'websocket.disconnect':
                return
            if message.get('text') and json.loads(message['text']).get('type') == 'stop':
                return
            raise ValueError('只接受已完成的录音，不能推送实时音频或播报指令')

    tasks = [asyncio.create_task(receive()), asyncio.create_task(send()), asyncio.create_task(watch_disconnect())]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@router.websocket('/ws')
async def realtime(browser: WebSocket):
    # CORS middleware doesn't protect WebSockets. Reject cross-site browser use.
    origin = browser.headers.get('origin')
    if origin and urlparse(origin).hostname != urlparse(str(browser.url)).hostname:
        await browser.close(code=1008)
        return
    await browser.accept()
    try:
        options = StartOptions.model_validate(await asyncio.wait_for(browser.receive_json(), 15))
        pcm = load_recording(options) if options.audio_file else await text_input_pcm(options.text)
        options.system_role = session_instructions(options.session_id) + '\n\n【本轮完整问题】\n' + options.text + '\n请结合完整问题作答，录音中的停顿不代表问题结束。'
        session_id = str(uuid4())
        headers = protocol.auth_headers(str(uuid4()))
        async with websockets.connect(protocol.ENDPOINT, extra_headers=headers,
                                      open_timeout=15, close_timeout=3, max_size=4 * 1024 * 1024) as upstream:
            started = False
            try:
                await upstream.send(protocol.encode_event('session.create', session=protocol.session_payload(options)))
                event = await receive_event(upstream, 'session.created')
                started = True
                session_id = event.get('session', {}).get('id', session_id)
                await browser.send_json({'type': 'ready', 'session_id': session_id})
                # Bound abandoned / unattended sessions to 30 minutes.
                await asyncio.wait_for(bridge(browser, upstream, pcm), 1800)
            finally:
                with suppress(Exception):
                    if started:
                        await finish_session(upstream)
    except WebSocketDisconnect:
        pass
    except (ValueError, ValidationError):
        with suppress(Exception):
            await browser.send_json({'type': 'error', 'message': '配置或输入无效，请检查凭据和输入参数'})
    except websockets.exceptions.InvalidStatusCode as exc:
        message = ('豆包鉴权失败（HTTP 403）：请核对 App 凭据与全双工资源 volc.service_type.10074 是否匹配；403 不一定表示未开通服务'
                   if exc.status_code == 403 else '豆包 WebSocket 握手失败，请检查服务状态及凭据')
        with suppress(Exception):
            await browser.send_json({'type': 'error', 'message': message})
    except asyncio.TimeoutError:
        with suppress(Exception):
            await browser.send_json({'type': 'error', 'message': '连接超时或已达到 30 分钟会话上限，请重新连接'})
    except Exception:
        with suppress(Exception):
            await browser.send_json({'type': 'error', 'message': '豆包连接失败，请检查网络、凭据、服务是否开通及额度'})
    finally:
        with suppress(Exception):
            await browser.close()
