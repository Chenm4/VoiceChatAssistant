from backend.test.workspace_case import WorkspaceTestCase, patch_path
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prompt_lab import service


class PromptLabTests(WorkspaceTestCase):
    def test_catalog_is_well_formed_and_does_not_expose_keys(self):
        catalog = service.get_catalog()
        self.assertGreaterEqual(len(catalog["prompts"]), 4)
        self.assertGreaterEqual(len(catalog["questions"]), 40)
        self.assertNotIn("api_key", json.dumps(catalog, ensure_ascii=False))
        for prompt in catalog["prompts"]:
            self.assertIn("{{question}}", prompt["user_prompt_template"])
        for source in catalog["sources"]:
            self.assertTrue(all(model.lower().startswith("qwen") for model in source["models"]))

    def test_run_path_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            service._run_path("../outside")

    def test_list_runs_reads_saved_json(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "abc.json").write_text(json.dumps({
                "id": "abc", "name": "测试", "status": "completed",
                "created_at": 1, "finished_at": 2, "completed": 1,
                "total": 1, "models": ["qwen-test"],
            }), encoding="utf-8")
            with patch_path(service, 'prompt_lab/data/runs', Path(directory)):
                summaries = service.list_runs()
        self.assertEqual(summaries[0]["name"], "测试")

    def test_edit_prompt_versions_previous_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompts_file = root / "prompts.json"
            history_dir = root / "history"
            history_dir.mkdir()
            prompts_file.write_text(json.dumps([{
                "id": "demo",
                "name": "旧模板",
                "description": "",
                "system_prompt": "旧 system",
                "user_prompt_template": "旧问题：{{question}}",
            }], ensure_ascii=False), encoding="utf-8")
            with patch_path(service, 'prompt_lab/prompts.json', prompts_file), patch_path(service, 'prompt_lab/data/prompt_history', history_dir
            ):
                saved = service.save_prompt({
                    "name": "新模板",
                    "description": "新版",
                    "system_prompt": "新 system",
                    "user_prompt_template": "新问题：{{question}}",
                }, "demo")
                versions = service.list_prompt_history("demo")

        self.assertEqual(saved["version"], 2)
        self.assertEqual([item["version"] for item in versions], [2, 1])
        self.assertEqual(versions[1]["system_prompt"], "旧 system")


if __name__ == "__main__":
    unittest.main()
