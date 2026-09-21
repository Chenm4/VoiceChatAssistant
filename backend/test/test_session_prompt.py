import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.api.models import Session, SessionConfig
from backend.services import session_prompt


def make_session(config: SessionConfig) -> Session:
    return Session(
        id="session-test",
        title="测试",
        created_at=1,
        updated_at=1,
        messages=[],
        session_config=config,
    )


class SessionPromptTests(unittest.TestCase):
    def test_new_session_config_snapshots_latest_spoken_template(self):
        with tempfile.TemporaryDirectory() as directory:
            prompts_file = Path(directory) / "prompts.json"
            prompts_file.write_text(json.dumps([
                {
                    "id": "spoken_keypoints",
                    "version": 2,
                    "system_prompt": "旧规则",
                    "user_prompt_template": "旧问题：{{question}}",
                },
                {
                    "id": "spoken_keypoints",
                    "version": 7,
                    "system_prompt": "新规则",
                    "user_prompt_template": "面试题：{{question}}",
                },
            ], ensure_ascii=False), encoding="utf-8")

            with patch.object(session_prompt, "PROMPTS_FILE", prompts_file):
                config = session_prompt.create_default_session_config()

        self.assertEqual(config.prompt_template_id, "spoken_keypoints")
        self.assertEqual(config.prompt_template_version, 7)
        self.assertEqual(config.system_prompt, "新规则")
        self.assertEqual(config.user_prompt_template, "面试题：{{question}}")
        self.assertEqual(config.background_mode, "shared")

    def test_shared_background_is_read_live_but_legacy_adds_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            background_file = Path(directory) / "background.json"
            background_file.write_text(
                json.dumps({"content": "第一版背景"}, ensure_ascii=False),
                encoding="utf-8",
            )
            shared = make_session(SessionConfig(
                system_prompt="回答规则",
                background_mode="shared",
            ))
            legacy = make_session(SessionConfig(
                system_prompt="旧版合并提示词",
                background_context="不应追加的旧背景字段",
            ))

            with patch.object(session_prompt, "BACKGROUND_FILE", background_file):
                first = session_prompt.compose_session_system_prompt(shared)
                background_file.write_text(
                    json.dumps({"content": "第二版背景"}, ensure_ascii=False),
                    encoding="utf-8",
                )
                second = session_prompt.compose_session_system_prompt(shared)
                legacy_prompt = session_prompt.compose_session_system_prompt(legacy)

        self.assertIn("第一版背景", first)
        self.assertNotIn("第一版背景", second)
        self.assertIn("第二版背景", second)
        self.assertEqual(legacy_prompt, "旧版合并提示词")

    def test_custom_and_none_background_modes(self):
        custom = make_session(SessionConfig(
            system_prompt="规则",
            background_mode="custom",
            background_context="会话专属背景",
        ))
        none = make_session(SessionConfig(
            system_prompt="规则",
            background_mode="none",
            background_context="不应发送",
        ))

        self.assertIn(
            "会话专属背景",
            session_prompt.compose_session_system_prompt(custom),
        )
        self.assertEqual(
            session_prompt.compose_session_system_prompt(none),
            "规则",
        )

    def test_user_prompt_template_is_a_snapshot_and_legacy_is_raw(self):
        templated = make_session(SessionConfig(
            user_prompt_template="面试题：{{question}}\n只回答这一题。",
        ))
        legacy = make_session(SessionConfig())

        self.assertEqual(
            session_prompt.render_session_user_prompt(templated, "什么是 Redis？"),
            "面试题：什么是 Redis？\n只回答这一题。",
        )
        self.assertEqual(
            session_prompt.render_session_user_prompt(legacy, "原始问题"),
            "原始问题",
        )


if __name__ == "__main__":
    unittest.main()
