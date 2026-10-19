from backend.test.workspace_case import WorkspaceTestCase, patch_path
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


class SessionPromptTests(WorkspaceTestCase):
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

            with patch_path(session_prompt, 'prompt_lab/prompts.json', prompts_file):
                config = session_prompt.create_default_session_config()

        self.assertEqual(config.prompt_template_id, "spoken_keypoints")
        self.assertEqual(config.prompt_template_version, 7)
        self.assertEqual(config.system_prompt, "新规则")
        self.assertEqual(config.user_prompt_template, "面试题：{{question}}")
        self.assertEqual(config.background_mode, "shared")
        self.assertEqual(config.source_name, '通义千问')
        self.assertEqual(config.models, ['qwen3.8-max', 'qwen3.7-plus'])
        self.assertEqual([(target.model, target.reasoning_effort) for target in config.model_targets],
                         [('qwen3.8-max', 'none'), ('qwen3.7-plus', 'low')])

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

            with patch_path(session_prompt, 'prompt_lab/background.json', background_file):
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

class AnswerHighlightPromptTests(WorkspaceTestCase):
    def test_opt_in_preserves_original_rules_and_background(self):
        config = SessionConfig(system_prompt='原规则', background_mode='custom', background_context='背景')
        session = make_session(config)
        original = session_prompt.compose_session_system_prompt(session)
        self.assertNotIn('answer_highlight', original)
        config.answer_highlight_enabled = True
        self.assertEqual(session_prompt.compose_session_system_prompt(session), original + '\n\n' + session_prompt.ANSWER_HIGHLIGHT_PROMPT)

    def test_scene_also_appends_protocol(self):
        from backend.api.models import PromptScene
        config = SessionConfig(system_prompt='规则', answer_highlight_enabled=True,
                               active_scene=PromptScene(id='test', name='测试'))
        prompt = session_prompt.compose_session_system_prompt(make_session(config))
        self.assertIn(session_prompt.ANSWER_HIGHLIGHT_PROMPT, prompt)
        self.assertLess(prompt.index(session_prompt.ANSWER_HIGHLIGHT_PROMPT), prompt.index('【当前场景】'))


if __name__ == "__main__":
    unittest.main()
