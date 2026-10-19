"""Authenticated workspace boundary. Never fall back to shared application data."""
import json
import os
import re
import tempfile
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
USERS_ROOT = PROJECT_ROOT / 'data' / 'users'
_current = ContextVar('user_workspace', default=None)
_workspaces = {}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class UserWorkspace:
    def __init__(self, username, root):
        self.username = username
        self.root = Path(root)
        self.settings = json.loads((self.root / 'settings.json').read_text(encoding='utf-8'))
        self._runtime = None
        self.tasks = {}
        self.locks = {}
        self.chat_loggers = {}

    def path(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError('用户目录之外的路径')
        return path

    @property
    def runtime(self):
        if self._runtime is None:
            from backend.api.models import ConfigList, ConfigSource, ConfigModel
            from backend.services.session_storage import SessionStorage
            sources = [ConfigSource(**item) for item in self.settings['OPENAI_CONFIG']]
            selected = self.settings['selection']
            source = next((s for s in sources if s.name == selected['source']), sources[0])
            storage = SessionStorage(self.root)
            index = storage.load_index()
            self._runtime = SimpleNamespace(
                config_sources=sources,
                current_config=ConfigList(sources=sources, current_source=source.name, current_model=selected['model']),
                api_config=ConfigModel(**self.settings.get('api_config', {
                    'api_key': source.api_key, 'base_url': source.base_url, 'model': selected['model']})),
                current_session_id=index.current_session_id or (index.sessions[0].id if index.sessions else None),
                current_session_cache=None, session_storage=storage,
                streaming_asr=None, streaming_asr_pool=None, openai_client=None,
                generation_epochs={},
            )
        return self._runtime

    def save_config(self):
        state = self.runtime
        self.settings['OPENAI_CONFIG'] = [source.dict() for source in state.config_sources]
        self.settings['selection'] = {'source': state.current_config.current_source, 'model': state.current_config.current_model}
        self.settings['api_config'] = state.api_config.dict()
        write_json(self.path('settings.json'), self.settings)


def workspace():
    value = _current.get()
    if value is None:
        raise RuntimeError('User workspace requires an authenticated context')
    return value


def user_state():
    return workspace().runtime


def user_path(relative):
    return workspace().path(relative)


def user_config(name):
    return workspace().settings[name]


def get_workspace(username):
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}', username):
        raise ValueError('无效用户名')
    key = (str(USERS_ROOT), username)
    if key not in _workspaces:
        _workspaces[key] = UserWorkspace(username, USERS_ROOT / username)
    return _workspaces[key]
