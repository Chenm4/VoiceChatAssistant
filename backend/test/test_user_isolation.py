"""Security regressions exercise real auth, routes, disk persistence and concurrent streams."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.api.routes import router
from backend.api.doubao_realtime import router as voice_router
from prompt_lab.router import router as lab_router
from backend.auth import session as auth
from backend.auth.bootstrap import bootstrap_users, fresh_settings
from backend.services import user_workspace as users
from backend.services.session_storage import SessionStorage


class UserIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patch_root = patch.object(users, 'USERS_ROOT', self.root / 'users')
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        # Fixture data, never copy real credentials/chat history into regression tests.
        legacy = self.root / 'legacy'
        users.write_json(legacy / 'data/sessions_index.json', {'sessions': [], 'current_session_id': None})
        users.write_json(legacy / 'prompt_lab/prompts.json', [{'id': 'spoken_keypoints', 'name': 'private', 'system_prompt': 'CHENBO ONLY', 'user_prompt_template': '{{question}}'}])
        users.write_json(legacy / 'prompt_lab/questions.json', [{'id': 'q', 'question': 'private question'}])
        users.write_json(legacy / 'prompt_lab/background.json', {'content': 'CHENBO BACKGROUND'})
        settings = fresh_settings()
        settings['OPENAI_CONFIG'][0]['api_key'] = 'chenbo-secret'
        settings['OPENAI_CONFIG'][0]['models'] = ['qwen-test']
        settings['selection']['model'] = 'qwen-test'
        with patch('backend.auth.bootstrap.PROJECT_ROOT', legacy), patch('backend.auth.bootstrap.legacy_settings', return_value=settings):
            bootstrap_users()
        self.app = FastAPI()
        self.app.add_middleware(auth.AuthenticationMiddleware)
        for api in (auth.router, router, lab_router, voice_router):
            self.app.include_router(api, prefix='/api')
        self.bo = TestClient(self.app)
        self.shuai = TestClient(self.app)
        self.addCleanup(self.bo.close)
        self.addCleanup(self.shuai.close)
        auth._attempts.clear()
        self.login(self.bo, 'chenbo')
        self.login(self.shuai, 'chenshuai')

    def login(self, client, username):
        response = client.post('/api/auth/login', json={'username': username, 'password': username})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('Max-Age=7776000', response.headers['set-cookie'])
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        self.assertIn('SameSite=strict', response.headers['set-cookie'])

    def test_every_api_requires_login_and_no_identity_spoofing(self):
        with TestClient(self.app) as client:
            for method, path in [('get', '/api/config'), ('post', '/api/chat'), ('get', '/api/sessions'), ('get', '/api/prompt-lab/catalog'), ('get', '/api/prompt-scenes'), ('get', '/api/attachments/a/b'), ('post', '/api/recording/start'), ('get', '/api/doubao-realtime/config')]:
                response = getattr(client, method)(path, headers={'X-Workspace-User': 'chenbo'})
                self.assertEqual(response.status_code, 401, path)
            with self.assertRaises(WebSocketDisconnect):
                with client.websocket_connect('/api/doubao-realtime/ws'):
                    pass
            self.assertEqual(client.post('/api/auth/login', json={'username': 'chenbo', 'password': 'wrong'}).status_code, 401)
        self.assertEqual(self.shuai.get('/api/config', headers={'X-Workspace-User': 'chenbo'}).status_code, 401)
        self.assertEqual(self.shuai.get('/api/config?workspace_user=chenbo').status_code, 401)
        self.assertEqual(self.bo.post('/api/sessions', headers={'Origin': 'https://evil.example'}).status_code, 403)

    def test_migration_is_private_idempotent_and_passwords_are_hashed(self):
        before = (users.USERS_ROOT / 'chenbo/settings.json').read_bytes()
        bootstrap_users()
        self.assertEqual(before, (users.USERS_ROOT / 'chenbo/settings.json').read_bytes())
        self.assertTrue((self.root / 'legacy/prompt_lab/background.json').exists())
        for name in ('chenbo', 'chenshuai'):
            account = json.loads((users.USERS_ROOT / name / 'account.json').read_text())
            self.assertNotEqual(account['password']['hash'], name)
        self.assertEqual(self.bo.get('/api/config').json()['sources'][0]['api_key'], 'chenbo-secret')
        self.assertEqual(self.shuai.get('/api/config').json()['sources'][0]['api_key'], '')
        catalog = self.shuai.get('/api/prompt-lab/catalog').json()
        self.assertEqual(catalog['prompts'], [])
        self.assertEqual(catalog['questions'], [])
        self.assertEqual(catalog['background']['content'], '')
        self.assertEqual(self.shuai.get('/api/prompt-scenes').json()['scenes'], [])

    def test_session_ids_cannot_cross_users_even_if_guessed(self):
        bo_session = self.bo.post('/api/sessions', params={'title': 'private title'}).json()['session']
        sid = bo_session['id']
        self.assertNotIn(sid, json.dumps(self.shuai.get('/api/sessions').json()))
        for method, suffix, body in [('get', '', None), ('post', '/switch', None), ('put', '/config', {}), ('get', '/config', None), ('get', '/audio/merged', None), ('put', '/title?title=stolen', None), ('delete', '', None)]:
            response = self.shuai.request(method, '/api/sessions/' + sid + suffix, json=body)
            self.assertEqual(response.status_code, 404, (method, suffix, response.text))
        self.assertEqual(self.bo.get('/api/sessions/' + sid).json()['title'], 'private title')
        self.assertEqual(self.shuai.post('/api/chat', json={'session_id': sid, 'message': 'steal'}).status_code, 404)

    def test_configs_prompts_background_and_runs_do_not_leak(self):
        self.shuai.post('/api/config/add', json={'name': 'Mine', 'api_key': 'shuai-key', 'base_url': 'https://example.test/v1', 'models': ['qwen-new']}).raise_for_status()
        self.shuai.post('/api/config/switch', params={'source_name': 'Mine', 'model': 'qwen-new'}).raise_for_status()
        self.assertNotIn('shuai-key', self.bo.get('/api/config').text)
        # Reopen the workspace to verify selection/key persistence rather than just memory.
        users._workspaces.pop((str(users.USERS_ROOT), 'chenshuai'))
        saved = self.shuai.get('/api/config').json()
        self.assertEqual(saved['current_source'], 'Mine')
        self.assertEqual(saved['current_model'], 'qwen-new')
        self.shuai.patch('/api/prompt-lab/background', json={'content': 'SHUAI ONLY'}).raise_for_status()
        self.assertEqual(self.bo.get('/api/prompt-lab/catalog').json()['background']['content'], 'CHENBO BACKGROUND')
        prompt = self.shuai.post('/api/prompt-lab/prompts', json={'name': 'Mine', 'system_prompt': 'SHUAI PROMPT', 'user_prompt_template': '{{question}}'}).json()
        self.assertNotIn('SHUAI PROMPT', self.bo.get('/api/prompt-lab/catalog').text)
        users.write_json(users.USERS_ROOT / 'chenbo/prompt_lab/data/runs/abcdef.json', {'id': 'abcdef', 'items': []})
        self.assertEqual(self.shuai.get('/api/prompt-lab/runs/abcdef').status_code, 404)

    def test_attachments_and_audio_cannot_cross_users(self):
        sid = self.bo.post('/api/sessions').json()['session']['id']
        png = b'\x89PNG\r\n\x1a\n' + b'example'
        uploaded = self.bo.post('/api/attachments/screenshots', data={'session_id': sid}, files={'screenshot': ('test.png', png, 'image/png')})
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        attachment = uploaded.json()
        path = f"/api/attachments/{sid}/{attachment['id']}"
        response = self.bo.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(self.shuai.get(path).status_code, 404)
        self.assertEqual(self.shuai.delete(path).status_code, 404)
        self.assertEqual(self.shuai.post('/api/attachments/screenshots', data={'session_id': sid}, files={'screenshot': ('test.png', png, 'image/png')}).status_code, 404)
        token = users._current.set(users.get_workspace('chenshuai'))
        try:
            from backend.api.doubao_realtime import load_recording, StartOptions
            with self.assertRaises(ValueError):
                load_recording(StartOptions(type='start', session_id=sid, audio_file='private.wav', text='hello'))
        finally:
            users._current.reset(token)

    def test_logout_revokes_cookie_and_stale_tab_identity(self):
        old = self.bo.cookies.get(auth.COOKIE)
        self.bo.post('/api/auth/logout').raise_for_status()
        self.assertEqual(self.bo.get('/api/config').status_code, 401)
        self.assertEqual(self.bo.get('/api/config', headers={'cookie': f'{auth.COOKIE}={old}'}).status_code, 401)
        self.login(self.bo, 'chenshuai')
        self.assertEqual(self.bo.get('/api/config', headers={'X-Workspace-User': 'chenbo'}).status_code, 401)
        self.assertEqual(self.bo.get('/api/auth/me').json(), {'username': 'chenshuai'})

    def test_concurrent_streams_threads_and_background_tasks_keep_owner(self):
        tasks = []
        @self.app.get('/api/isolation-probe')
        async def probe():
            async def background():
                await asyncio.sleep(.02)
                users.write_json(users.user_path('probe.json'), {'owner': users.workspace().username})
            tasks.append(asyncio.create_task(background()))
            async def stream():
                for i in range(3):
                    await asyncio.sleep(.01)
                    owner = await asyncio.to_thread(lambda: users.workspace().username)
                    yield owner + '\n'
            return StreamingResponse(stream())
        async def exercise():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
                async def request(client_cookie):
                    return await client.get('/api/isolation-probe', headers={'cookie': f'{auth.COOKIE}={client_cookie}'})
                bo, shuai = await asyncio.gather(request(self.bo.cookies.get(auth.COOKIE)), request(self.shuai.cookies.get(auth.COOKIE)))
                await asyncio.gather(*tasks)
                self.assertEqual(bo.text, 'chenbo\n' * 3)
                self.assertEqual(shuai.text, 'chenshuai\n' * 3)
        asyncio.run(exercise())
        for name in ('chenbo', 'chenshuai'):
            self.assertEqual(json.loads((users.USERS_ROOT / name / 'probe.json').read_text())['owner'], name)
        with self.assertRaises(RuntimeError):
            users.user_path('settings.json')

    def test_all_voice_credentials_and_runtime_caches_are_private(self):
        from backend.utils.sauc_client import RequestBuilder
        from backend.services.doubao_realtime import credentials
        from backend.utils.chat_logger import get_session_logger
        from backend.utils.logger import get_api_logger
        states = []
        for username in ('chenbo', 'chenshuai'):
            token = users._current.set(users.get_workspace(username))
            try:
                settings = users.workspace().settings
                settings['BYTEDANCE_ASR_CONFIG']['access_key'] = username + '-asr'
                settings['DOUBAO_REALTIME']['access_token'] = username + '-realtime'
                self.assertEqual(RequestBuilder.new_auth_headers()['X-Api-Access-Key'], username + '-asr')
                self.assertEqual(credentials()[1], username + '-realtime')
                states.append(users.user_state())
                users.user_state().generation_epochs['same-session-id'] = username
                log = get_session_logger('same-session-id')
                self.assertTrue(log.log_file.is_relative_to(users.workspace().root.resolve()))
                get_api_logger().info(username + '-private-log')
            finally:
                users._current.reset(token)
        self.assertIsNot(states[0], states[1])
        self.assertEqual(states[0].generation_epochs['same-session-id'], 'chenbo')
        self.assertEqual(states[1].generation_epochs['same-session-id'], 'chenshuai')
        self.assertNotIn('chenshuai-private-log', (users.USERS_ROOT / 'chenbo/logs/api.log').read_text())
        self.assertNotIn('chenbo-private-log', (users.USERS_ROOT / 'chenshuai/logs/api.log').read_text())

    def test_path_traversal_is_rejected(self):
        storage = SessionStorage(users.USERS_ROOT / 'chenshuai')
        for name in ('../chenbo/settings', '/tmp/outside', '../../account', 'a/b'):
            with self.assertRaises(ValueError):
                storage._get_session_path(name, 1)
        token = users._current.set(users.get_workspace('chenshuai'))
        try:
            with self.assertRaises(ValueError):
                users.user_path('../chenbo/settings.json')
        finally:
            users._current.reset(token)
