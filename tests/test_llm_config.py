import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from dotenv import load_dotenv


class LLMConfigTest(unittest.TestCase):
    def test_environment_overrides_dotenv_and_reaches_client(self):
        self._check_endpoint(
            {"OPENAI_BASE_URL": "http://10.7.7.136:8080/v1"},
            "http://10.7.7.136:8080/v1",
        )

    def test_dotenv_supplies_endpoint_when_environment_is_unset(self):
        self._check_endpoint({}, "http://10.7.7.79:8080/v1")

    def _check_endpoint(self, environment, expected):
        module_path = Path(__file__).resolve().parents[1] / "src/libs/llm/main.py"
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "LLM_PROVIDER=openai-compatible\n"
                "OPENAI_BASE_URL=http://10.7.7.79:8080/v1\n"
                "OPENAI_MODEL=test-model\n"
            )
            with patch.dict(os.environ, environment, clear=True):
                with patch(
                    "dotenv.load_dotenv",
                    side_effect=lambda path, **kwargs: load_dotenv(env_path, **kwargs),
                ):
                    module = runpy.run_path(str(module_path))
                config = module["load_llm_config"]()
                self.assertEqual(config.base_url, expected)
                client = Mock()
                with patch.dict(
                    module["create_chat_model"].__globals__, ChatOpenAI=client
                ):
                    module["create_chat_model"](config)
                    self.assertEqual(
                        client.call_args.kwargs["base_url"], expected
                    )


if __name__ == "__main__":
    unittest.main()
