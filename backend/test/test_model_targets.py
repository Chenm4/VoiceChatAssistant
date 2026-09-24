import unittest
from unittest.mock import patch
from pydantic import ValidationError

from backend.api import routes
from backend.api.models import ConfigSource, ModelTarget, SessionConfig


class ModelTargetTests(unittest.TestCase):
    def setUp(self):
        self.sources = [
            ConfigSource(
                name="SourceA",
                api_key="key-a",
                base_url="https://a.example/v1",
                models=["shared-model", "model-a"],
            ),
            ConfigSource(
                name="SourceB",
                api_key="key-b",
                base_url="https://b.example/v1",
                models=["shared-model", "model-b"],
            ),
        ]

    def test_resolves_cross_source_targets_with_distinct_keys(self):
        config = SessionConfig(model_targets=[
            ModelTarget(
                source_name="SourceA",
                model="shared-model",
                reasoning_effort="medium",
            ),
            ModelTarget(source_name="SourceB", model="shared-model"),
        ])

        with patch.object(routes, "config_sources", self.sources):
            targets = routes.resolve_model_targets(config)

        self.assertEqual(
            [target["key"] for target in targets],
            ["SourceA::shared-model", "SourceB::shared-model"],
        )
        self.assertEqual(targets[0]["source"].base_url, "https://a.example/v1")
        self.assertEqual(targets[1]["source"].base_url, "https://b.example/v1")
        self.assertEqual(targets[0]["reasoning_effort"], "medium")
        self.assertEqual(targets[1]["reasoning_effort"], "none")

    def test_legacy_single_source_config_still_resolves(self):
        config = SessionConfig(source_name="SourceA", models=["model-a"])

        with patch.object(routes, "config_sources", self.sources):
            targets = routes.resolve_model_targets(config)

        self.assertEqual(targets[0]["key"], "SourceA::model-a")

    def test_requested_composite_model_selects_exact_source(self):
        with patch.object(routes, "config_sources", self.sources):
            targets = routes.resolve_model_targets(None, "SourceB::shared-model")

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["source_name"], "SourceB")

    def test_provider_specific_reasoning_parameters(self):
        qwen = ConfigSource(
            name="Qwen",
            api_key="key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            models=["qwen3.8-max"],
        )
        openrouter = ConfigSource(
            name="OpenRouter",
            api_key="key",
            base_url="https://openrouter.ai/api/v1",
            models=["some-reasoning-model"],
        )

        self.assertEqual(
            routes.get_chat_completion_extra_params(qwen, "qwen3.8-max", "none"),
            {"extra_body": {"enable_thinking": False}},
        )
        self.assertEqual(
            routes.get_chat_completion_extra_params(qwen, "qwen3.8-max", "medium"),
            {"extra_body": {"reasoning_effort": "medium"}},
        )
        self.assertEqual(
            routes.get_chat_completion_extra_params(
                openrouter, "some-reasoning-model", "low"
            ),
            {"extra_body": {"reasoning": {"effort": "low"}}},
        )

    def test_config_source_rejects_non_ascii_api_key(self):
        with self.assertRaises(ValidationError):
            ConfigSource(
                name="Qwen",
                api_key="误粘贴的内容",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                models=["qwen3.7-plus"],
            )


if __name__ == "__main__":
    unittest.main()
