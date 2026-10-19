import base64
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from backend.api.models import ChatMessage, ChatRequest, MessageAttachment, MessageUpdateRequest, ModelTarget, RegenerateMessageRequest, Session, SessionConfig
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

    def test_edit_can_replace_and_remove_screenshots(self):
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            session_id = "session_test"
            folder = root / session_id
            folder.mkdir()
            old_id, new_id = "a" * 24, "b" * 24
            (folder / f"{old_id}.webp").write_bytes(b"RIFFxxxxWEBPold")
            (folder / f"{new_id}.webp").write_bytes(b"RIFFxxxxWEBPnew")
            old = MessageAttachment(id=old_id, mime_type="image/webp", filename=f"{old_id}.webp")
            message = ChatMessage(id="question", role="user", content="old", attachments=[old])
            session = Session(id=session_id, title="test", created_at=1, updated_at=1, messages=[message])
            with patch.object(routes, "SCREENSHOT_DIR", root), \
                 patch.object(routes.session_storage, "load_session", return_value=session), \
                 patch.object(routes.session_storage, "save_session"):
                asyncio.run(routes.update_message(
                    session_id, message.id,
                    MessageUpdateRequest(content="new", attachment_ids=[new_id]),
                ))
                self.assertEqual([item.id for item in message.attachments], [new_id])
                self.assertFalse((folder / f"{old_id}.webp").exists())
                self.assertTrue((folder / f"{new_id}.webp").exists())

    def test_pending_image_cleanup_cannot_delete_saved_message_image(self):
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            folder = root / "session_test"
            folder.mkdir()
            image_id = "a" * 24
            path = folder / f"{image_id}.webp"
            path.write_bytes(b"RIFFxxxxWEBPimage")
            attachment = MessageAttachment(id=image_id, mime_type="image/webp", filename=path.name)
            session = Session(
                id="session_test", title="test", created_at=1, updated_at=1,
                messages=[ChatMessage(id="question", role="user", content="image", attachments=[attachment])],
            )
            with patch.object(routes, "SCREENSHOT_DIR", root), \
                 patch.object(routes.session_storage, "load_session", return_value=session):
                with self.assertRaises(HTTPException) as result:
                    asyncio.run(routes.delete_unused_screenshot(session.id, image_id))
            self.assertEqual(result.exception.status_code, 409)
            self.assertTrue(path.exists())

    def test_model_rerun_keeps_other_parallel_answer(self):
        target = ModelTarget(source_name="test", model="model-a", reasoning_effort="low")
        question = ChatMessage(id="question", role="user", content="hello", children_ids=["answer"])
        answer = ChatMessage(
            id="answer", parent_id="question", role="assistant", content="",
            type="multi_model", is_parallel_response=True,
            parallel_models=[
                {"model_key": "test::model-a", "content": "old a", "model_info": {"name": "model-a", "provider": "test"}},
                {"model_key": "test::model-b", "content": "old b", "model_info": {"name": "model-b", "provider": "test"}},
            ],
        )
        session = Session(
            id="session_test", title="test", created_at=1, updated_at=1,
            messages=[question, answer], session_config=SessionConfig(model_targets=[target]),
        )
        source = SimpleNamespace(name="test", api_key="test-key", base_url="https://example.invalid")
        provider_target = {"key": "test::model-a", "model": "model-a", "source_name": "test", "source": source, "reasoning_effort": "low"}
        chunk = SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="new a"))])
        completion = Mock()
        completion.chat.completions.create.return_value = iter([
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None, reasoning_content='thinking'))]),
            chunk,
        ])

        async def run():
            response = await routes.regenerate_message(
                session.id, question.id,
                RegenerateMessageRequest(message_id=question.id, new_content="hello", model="test::model-a", reasoning_effort="high"),
            )
            return [part async for part in response.body_iterator]

        with patch.object(routes.session_storage, "load_session", return_value=session), \
             patch.object(routes.session_storage, "save_session"), \
             patch.object(routes, "resolve_model_targets", return_value=[provider_target]), \
             patch.object(routes, "build_message_path", return_value=[question]), \
             patch.object(routes, "OpenAI", return_value=completion), \
             patch.object(routes, "log_model_request_context"), \
             patch.object(routes, "log_provider_request", return_value={}):
            chunks = asyncio.run(run())

        self.assertTrue(any('"type": "done"' in part for part in chunks))
        types = [__import__('json').loads(part.removeprefix('data: ').strip())['type'] for part in chunks]
        self.assertLess(types.index('targeted_start'), types.index('reasoning'))
        self.assertLess(types.index('reasoning'), types.index('content'))
        self.assertLess(types.index('content'), types.index('done'))
        self.assertEqual(answer.parallel_models[0]['reasoning_content'], 'thinking')
        self.assertEqual(len(session.messages), 2)
        self.assertEqual(question.children_ids, ["answer"])
        self.assertEqual(answer.parallel_models[0]["content"], "new a")
        self.assertEqual(answer.parallel_models[0]["model_info"]["reasoning_effort"], "high")
        self.assertEqual(answer.parallel_models[1]["content"], "old b")
        self.assertEqual(provider_target["reasoning_effort"], "high")

    def test_concurrent_chat_responses_do_not_overwrite_each_other(self):
        session = Session(
            id="session_test", title="test", created_at=1, updated_at=1,
            session_config=SessionConfig(model_targets=[ModelTarget(source_name="test", model="model-a")]),
        )
        stored = {session.id: session.model_copy(deep=True)}

        def load(session_id):
            item = stored.get(session_id)
            return item.model_copy(deep=True) if item else None

        def save(item):
            stored[item.id] = item.model_copy(deep=True)
            return True

        source = SimpleNamespace(name="test", api_key="test-key", base_url="https://example.invalid")
        provider_target = {"key": "test::model-a", "model": "model-a", "source_name": "test", "source": source, "reasoning_effort": "none"}
        chunk = SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="reply"))])
        completion = Mock()
        completion.chat.completions.create.side_effect = lambda **kwargs: iter([chunk])

        async def run():
            first = await routes.chat(ChatRequest(message="first", session_id=session.id))
            second = await routes.chat(ChatRequest(message="second", session_id=session.id))
            # Persisted question IDs are available before consuming any model tokens.
            questions = stored[session.id].messages
            self.assertEqual(first.headers['X-User-Message-Id'], questions[0].id)
            self.assertEqual(second.headers['X-User-Message-Id'], questions[1].id)
            completion.chat.completions.create.assert_not_called()
            async def consume(response):
                return [part async for part in response.body_iterator]
            await asyncio.gather(consume(first), consume(second))

        with patch.object(routes.session_storage, "load_session", side_effect=load), \
             patch.object(routes.session_storage, "save_session", side_effect=save), \
             patch.object(routes, "resolve_model_targets", return_value=[provider_target]), \
             patch.object(routes, "OpenAI", return_value=completion), \
             patch.object(routes, "log_model_request_context"), \
             patch.object(routes, "log_provider_request", return_value={}), \
             patch.object(routes, "log_model_interaction"):
            asyncio.run(run())

        saved = stored[session.id]
        self.assertEqual([message.role for message in saved.messages], ["user", "assistant", "user", "assistant"])
        self.assertEqual([message.content for message in saved.messages], ["first", "reply", "second", "reply"])
        self.assertEqual(saved.messages[0].children_ids, [saved.messages[1].id])
        self.assertEqual(saved.messages[2].children_ids, [saved.messages[3].id])


if __name__ == "__main__":
    unittest.main()
