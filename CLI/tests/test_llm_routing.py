import os
import unittest
from unittest import mock

from aira.llm import LLMConfig, provider_health_snapshot


class ProviderHealthSnapshotTests(unittest.TestCase):
    def test_local_openai_compatible_is_detected(self):
        with mock.patch.dict(
            os.environ,
            {
                "AIRA_OPENAI_BASE_URL": "http://localhost:1234/v1",
                "AIRA_OPENAI_MODEL": "gpt-oss-120b",
            },
            clear=False,
        ):
            snapshot = provider_health_snapshot(LLMConfig())

        self.assertTrue(snapshot["ok"])
        self.assertIn("openai-compatible", snapshot["configured_providers"])
        self.assertEqual(snapshot["providers"]["openai-compatible"]["model"], "gpt-oss-120b")

    def test_ollama_defaults_host_when_model_present(self):
        with mock.patch.dict(os.environ, {"AIRA_OLLAMA_MODEL": "qwen3:32b"}, clear=False):
            snapshot = provider_health_snapshot(LLMConfig())

        self.assertIn("ollama", snapshot["configured_providers"])
        self.assertEqual(snapshot["providers"]["ollama"]["base_url"], "http://127.0.0.1:11434")


if __name__ == "__main__":
    unittest.main()
