from backend.test.workspace_case import WorkspaceTestCase
import base64
import hashlib
import unittest
from unittest.mock import patch

from backend.api import routes
from backend.api.models import ConfigSource


class ProviderRequestPreviewTests(WorkspaceTestCase):
    def test_request_preview_keeps_history_and_options_without_image_data_or_keys(self):
        image = b"example image bytes"
        encoded = base64.b64encode(image).decode("ascii")
        source = ConfigSource(
            name="Example", api_key="private-key",
            base_url="https://example.test/v1", models=["model"],
        )
        params = {
            "model": "model",
            "messages": [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "history question"},
                {"role": "user", "content": [
                    {"type": "text", "text": "current question"},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{encoded}",
                    }},
                ]},
            ],
            "extra_body": {"api_key": "nested-secret", "reasoning": {"effort": "medium"}},
            "stream": True,
        }

        with patch.object(routes.logger, "info"):
            preview = routes.log_provider_request(source, params)

        self.assertEqual(preview["parameters"]["messages"][1]["content"], "history question")
        self.assertEqual(preview["parameters"]["extra_body"]["api_key"], "[REDACTED]")
        self.assertEqual(preview["parameters"]["extra_body"]["reasoning"]["effort"], "medium")
        image_part = preview["parameters"]["messages"][2]["content"][1]
        self.assertEqual(image_part["image_url"]["url"]["sha256"], hashlib.sha256(image).hexdigest())
        self.assertEqual(image_part["image_url"]["url"]["mime_type"], "image/png")
        self.assertNotIn(encoded, str(preview))
        self.assertNotIn("private-key", str(preview))


if __name__ == "__main__":
    unittest.main()
