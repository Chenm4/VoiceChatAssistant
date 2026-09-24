import unittest

from backend.api.routes import trim_history_context, _redact_request_secrets
from backend.services.token_budget import count_tokens


class TokenBudgetTests(unittest.TestCase):
    def test_history_is_trimmed_by_tokens_and_keeps_system_message(self):
        messages = [
            {"role": "system", "content": "规则"},
            {"role": "user", "content": "旧问题" * 30},
            {"role": "assistant", "content": "旧回答"},
            {"role": "user", "content": "新问题"},
        ]

        result = trim_history_context(messages, 8, "gpt-4o")

        self.assertEqual([message["role"] for message in result], ["system", "user"])
        self.assertEqual(result[-1]["content"], "新问题")

    def test_oversized_latest_turn_stays_within_budget(self):
        messages = [{"role": "user", "content": "中文问题" * 100}]

        result = trim_history_context(messages, 9, "gpt-4o")

        self.assertEqual(len(result), 1)
        self.assertLessEqual(count_tokens(result[0]["content"], "gpt-4o"), 9)
        self.assertTrue(result[0]["content"])

    def test_nested_credentials_are_redacted_without_hiding_other_parameters(self):
        value = {"api_key": "secret", "extra_body": {"access_token": "secret", "max_tokens": 100}}

        result = _redact_request_secrets(value)

        self.assertEqual(result["api_key"], "[REDACTED]")
        self.assertEqual(result["extra_body"]["access_token"], "[REDACTED]")
        self.assertEqual(result["extra_body"]["max_tokens"], 100)


if __name__ == "__main__":
    unittest.main()
