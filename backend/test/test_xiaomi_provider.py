from backend.test.workspace_case import WorkspaceTestCase, user_state
import asyncio
import unittest
from backend.api import routes
from backend.api.models import ConfigSource, ModelTarget, SessionConfig
from unittest.mock import patch


class XiaomiProviderTests(WorkspaceTestCase):
    def test_thinking_uses_mimo_parameter_without_affecting_other_models(self):
        xiaomi = ConfigSource(name='小米 MiMo', api_key='test', base_url='https://api.xiaomimimo.com/v1', models=['mimo-v2.6-pro-ultraspeed'])
        other = ConfigSource(name='openrouter', api_key='test', base_url='https://openrouter.ai/api/v1', models=['test-model'])
        config = SessionConfig(model_targets=[
            ModelTarget(source_name=xiaomi.name, model=xiaomi.models[0], reasoning_effort='high'),
            ModelTarget(source_name=other.name, model=other.models[0], reasoning_effort='low'),
        ])
        with patch.object(user_state(), 'config_sources', [xiaomi, other]):
            targets = routes.resolve_model_targets(config)
        payloads = [routes.get_chat_completion_extra_params(t['source'], t['model'], t['reasoning_effort']) for t in targets]
        self.assertEqual(payloads[0], {'extra_body': {'thinking': {'type': 'enabled'}}})
        self.assertEqual(payloads[1], {'extra_body': {'reasoning': {'effort': 'low'}}})
        self.assertEqual(routes.get_chat_completion_extra_params(xiaomi, xiaomi.models[0], 'none'), {'extra_body': {'thinking': {'type': 'disabled'}}})

    def test_scene_route_is_registered_and_returns_catalog(self):
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(routes.router, prefix="/api")
        from fastapi.testclient import TestClient
        response = TestClient(app).get('/api/prompt-scenes')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json()['scenes'], list)
