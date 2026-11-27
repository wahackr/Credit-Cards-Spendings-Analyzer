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


class ListModelsTest(unittest.TestCase):
    def setUp(self):
        from libs.llm import main as llm_main

        self.llm_main = llm_main

    def test_returns_sorted_unique_model_ids(self):
        client = Mock()
        client.models.list.return_value = Mock(
            data=[Mock(id="gpt-b"), Mock(id="gpt-a"), Mock(id="gpt-a")]
        )
        with patch.dict(
            os.environ,
            {"OPENAI_BASE_URL": "http://gw:8080/v1", "OPENAI_API_KEY": "k"},
            clear=True,
        ):
            with patch.object(self.llm_main, "OpenAI", return_value=client):
                models, error = self.llm_main.list_available_models()
        self.assertIsNone(error)
        self.assertEqual(models, ["gpt-a", "gpt-b"])

    def test_missing_base_url_reports_error_without_calling_client(self):
        client = Mock()
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(self.llm_main, "OpenAI", return_value=client) as ctor:
                models, error = self.llm_main.list_available_models()
        self.assertEqual(models, [])
        self.assertIsNotNone(error)
        ctor.assert_not_called()

    def test_endpoint_failure_is_returned_as_error(self):
        client = Mock()
        client.models.list.side_effect = RuntimeError("connection refused")
        with patch.dict(
            os.environ,
            {"OPENAI_BASE_URL": "http://gw:8080/v1", "OPENAI_API_KEY": "k"},
            clear=True,
        ):
            with patch.object(self.llm_main, "OpenAI", return_value=client):
                models, error = self.llm_main.list_available_models()
        self.assertEqual(models, [])
        self.assertIn("connection refused", error)


if __name__ == "__main__":
    unittest.main()
