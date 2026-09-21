import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.api.models import MessageAttachment, SessionConfig
from backend.api import routes


class ScreenshotChatTests(unittest.TestCase):
    def test_default_screenshot_prompt_requires_answer_first(self):
        prompt = SessionConfig().screenshot_prompt
        self.assertIn("开头", prompt)
        self.assertIn("最终答案", prompt)
        self.assertIn("时间复杂度", prompt)

    def test_multimodal_content_embeds_stored_screenshot(self):
        with tempfile.TemporaryDirectory() as directory_name:
            screenshot_root = Path(directory_name)
            session_id = "session_test"
            attachment_id = "a" * 24
            image_bytes = b"RIFFxxxxWEBPtest-image"
            directory = screenshot_root / session_id
            directory.mkdir()
            (directory / f"{attachment_id}.webp").write_bytes(image_bytes)
            attachment = MessageAttachment(
                id=attachment_id,
                mime_type="image/webp",
                filename=f"{attachment_id}.webp",
                size=len(image_bytes),
            )

            with patch.object(routes, "SCREENSHOT_DIR", screenshot_root):
                content = routes._multimodal_user_content(
                    session_id, "answer this question", [attachment]
                )

        self.assertEqual(
            content[0], {"type": "text", "text": "answer this question"}
        )
        self.assertEqual(content[1]["type"], "image_url")
        self.assertEqual(
            content[1]["image_url"]["url"],
            "data:image/webp;base64," + base64.b64encode(image_bytes).decode("ascii"),
        )

    def test_request_log_preview_never_contains_image_data(self):
        content = [
            {"type": "text", "text": "question"},
            {
                "type": "image_url",
                "image_url": {"url": "data:image/webp;base64," + "A" * 1000},
            },
        ]

        preview = routes._content_log_preview(content, 160, False)

        self.assertEqual(preview, "question [images=1]")
        self.assertNotIn("AAAA", preview)


if __name__ == "__main__":
    unittest.main()
