"""Authentication is applied to the whole ASGI request, including streams and sockets."""
import asyncio
import hashlib
import hmac
import json
import secrets
import time
from http.cookies import SimpleCookie
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse
from backend.services.user_workspace import _current, get_workspace, workspace

COOKIE = 'voice_session'
TTL = 7 * 24 * 3600
_sessions = {}
_attempts = {}
router = APIRouter(prefix='/auth', tags=['登录'])


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=256)


def token_from(scope):
    cookie = SimpleCookie()
    try:
        cookie.load(HTTPConnection(scope).headers.get('cookie', ''))
        return cookie[COOKIE].value if COOKIE in cookie else ''
    except Exception:
        return ''


def authenticated_user(scope):
    record = _sessions.get(token_from(scope))
    if not record or record['expires'] <= time.time():
        return None
    return record['username']


@router.post('/login')
async def login(body: Login, request: Request, response: Response):
    address = request.client.host if request.client else 'local'
    now = time.time()
    attempts = [stamp for stamp in _attempts.get(address, []) if stamp > now - 60]
    if len(attempts) >= 10:
        raise HTTPException(429, '尝试次数过多，请稍后再试')
    attempts.append(now)
    _attempts[address] = attempts
    try:
        from backend.services.user_workspace import USERS_ROOT
        if body.username not in ('chenbo', 'chenshuai'):
            raise ValueError()
        account = json.loads((USERS_ROOT / body.username / 'account.json').read_text())
        saved = account['password']
        digest = await asyncio.to_thread(hashlib.pbkdf2_hmac, 'sha256', body.password.encode(), bytes.fromhex(saved['salt']), 600000)
        valid = hmac.compare_digest(saved['hash'], digest.hex())
    except (ValueError, OSError, KeyError):
        valid = False
    if not valid:
        raise HTTPException(401, '用户名或密码错误')
    _attempts.pop(address, None)
    # Replacing a cookie revokes its old credential, including an old tab's requests.
    previous = authenticated_user(request.scope)
    if previous:
        previous_workspace = get_workspace(previous)
        context = _current.set(previous_workspace)
        try:
            await stop_recording()
        finally:
            _current.reset(context)
    _sessions.pop(token_from(request.scope), None)
    token = secrets.token_urlsafe(32)
    _sessions[token] = {'username': body.username, 'expires': now + TTL}
    response.set_cookie(COOKIE, token, httponly=True, samesite='strict', secure=request.url.scheme == 'https' or urlparse(request.headers.get('origin', '')).scheme == 'https', max_age=TTL)
    return {'username': body.username}


@router.get('/me')
async def me():
    return {'username': workspace().username}


@router.post('/logout')
async def logout(request: Request, response: Response):
    _sessions.pop(token_from(request.scope), None)
    await stop_recording()
    response.delete_cookie(COOKIE)
    return {'success': True}


async def stop_recording():
    from backend.api.routes import attach_recording_to_session
    state = workspace().runtime
    if state.streaming_asr:
        recorder = state.streaming_asr
        state.streaming_asr = None
        try:
            await recorder.stop_streaming()
            attach_recording_to_session(getattr(recorder, 'session_id', None), recorder.saved_audio_file)
        except Exception:
            from backend.utils.logger import get_api_logger
            get_api_logger().exception('退出时清理录音失败')
        finally:
            state.streaming_asr_pool = None


class AuthenticationMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] not in ('http', 'websocket') or not scope['path'].startswith('/api'):
            return await self.app(scope, receive, send)
        connection = HTTPConnection(scope)
        origin = connection.headers.get('origin')
        # Same-host frontends may use a different development port.
        if origin and urlparse(origin).hostname != connection.url.hostname:
            return await self.reject(scope, receive, send, 403, '不允许跨站请求')
        if scope['path'] == '/api/auth/login' and scope['type'] == 'http':
            return await self.app(scope, receive, self.no_cache(send))
        username = authenticated_user(scope)
        expected = connection.headers.get('x-workspace-user') or connection.query_params.get('workspace_user')
        if not username or (expected and expected != username):
            return await self.reject(scope, receive, send, 401, '请先登录')
        token = _current.set(get_workspace(username))
        try:
            await self.app(scope, receive, self.no_cache(send))
        finally:
            _current.reset(token)

    @staticmethod
    def no_cache(send):
        async def wrapped(message):
            if message['type'] == 'http.response.start':
                message['headers'] = [(k, v) for k, v in message.get('headers', []) if k.lower() != b'cache-control'] + [(b'cache-control', b'no-store')]
            await send(message)
        return wrapped

    @staticmethod
    async def reject(scope, receive, send, status, detail):
        if scope['type'] == 'websocket':
            await send({'type': 'websocket.close', 'code': 1008})
        else:
            await JSONResponse({'detail': detail}, status_code=status, headers={'Cache-Control': 'no-store'})(scope, receive, send)
