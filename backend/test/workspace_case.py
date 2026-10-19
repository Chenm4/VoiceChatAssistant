"""Temporary authenticated workspace for service-level regression tests."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch
from backend.auth.bootstrap import fresh_settings
from backend.services.user_workspace import UserWorkspace, _current, write_json, user_state, workspace, user_path


class WorkspaceMixin:
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        settings = fresh_settings()
        settings['OPENAI_CONFIG'] = [{'name': '通义千问', 'models': ['qwen3.8-max', 'qwen3.7-plus'], 'api_key': 'test-key', 'base_url': 'https://example.test/v1'}]
        settings['selection'] = {'source': '通义千问', 'model': 'qwen3.8-max'}
        settings['DEFAULT_SESSION_CONFIG'] = {'source_name': '通义千问', 'models': ['qwen3.8-max', 'qwen3.7-plus'], 'model_targets': [
            {'source_name': '通义千问', 'model': 'qwen3.8-max', 'reasoning_effort': 'none'},
            {'source_name': '通义千问', 'model': 'qwen3.7-plus', 'reasoning_effort': 'low'}]}
        write_json(root / 'settings.json', settings)
        for name in ('prompts.json', 'questions.json', 'background.json'):
            source = Path(__file__).resolve().parents[2] / 'prompt_lab' / name
            target = root / 'prompt_lab' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for name in ('prompt_lab/data/runs', 'prompt_lab/data/prompt_history', 'voices', 'screenshots'):
            (root / name).mkdir(parents=True, exist_ok=True)
        self.test_workspace = UserWorkspace('test', root)
        token = _current.set(self.test_workspace)
        self.addCleanup(_current.reset, token)


class WorkspaceTestCase(WorkspaceMixin, unittest.TestCase):
    pass


class WorkspaceAsyncTestCase(WorkspaceMixin, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.async_workspace_token = _current.set(self.test_workspace)

    async def asyncTearDown(self):
        _current.reset(self.async_workspace_token)


@contextmanager
def patch_path(module, relative, target):
    original = module.user_path
    with patch.object(module, 'user_path', side_effect=lambda name: target if name == relative else original(name)):
        yield
