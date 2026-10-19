import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.api.routes import stop_recording
from backend.services.browser_recording import BrowserStreamingASR, require_asr_credentials
from backend.services.user_workspace import user_state, workspace

router = APIRouter(prefix='/recording', tags=['浏览器录音'])


@router.websocket('/browser')
async def browser_recording(socket: WebSocket):
    await socket.accept()
    recorder = None
    try:
        async with workspace().locks.setdefault('browser-recording', asyncio.Lock()):
            if user_state().streaming_asr:
                raise ValueError('当前账号已有录音，请先停止原录音')
            require_asr_credentials()
            recorder = BrowserStreamingASR()
            recorder.session_id = user_state().current_session_id
            if not recorder.session_id:
                raise ValueError('请先创建或选择会话')
            user_state().streaming_asr = recorder
            recorder._task = asyncio.create_task(recorder.start_streaming())
            recorder._task.add_done_callback(lambda task: None if task.cancelled() else task.exception())
        await asyncio.wait_for(recorder.wait_until_recording(), timeout=15)
        await socket.send_json({'type': 'ready', 'success': True})
        while True:
            message = await asyncio.wait_for(socket.receive(), timeout=20)
            if message['type'] == 'websocket.disconnect':
                break
            if user_state().streaming_asr is not recorder:
                raise ValueError('当前录音已结束或已被替换')
            if message.get('bytes') is not None:
                recorder.receive_pcm(message['bytes'])
                await socket.send_json({'type': 'ack'})
            else:
                control = json.loads(message.get('text') or '{}')
                if control.get('type') != 'stop':
                    raise ValueError('不支持的录音指令')
                result = await stop_recording(finalize=control.get('finalize', True) is True)
                await socket.send_json({'type': 'stopped', **result.dict()})
                break
    except WebSocketDisconnect:
        pass
    except Exception as error:
        try:
            await socket.send_json({'type': 'error', 'message': str(error)})
        except (RuntimeError, WebSocketDisconnect):
            pass
    finally:
        if recorder is not None and user_state().streaming_asr is recorder:
            await stop_recording(finalize=False)
        try:
            await socket.close()
        except (RuntimeError, WebSocketDisconnect):
            pass
