import unittest
from unittest.mock import patch

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
            ModelTarget(source_name="SourceA", model="shared-model"),
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


if __name__ == "__main__":
    unittest.main()
