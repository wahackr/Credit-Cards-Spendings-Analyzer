import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from libs.llm.main import LLMConfig, OPENAI_COMPATIBLE
from libs.tools.statement_reader import read_statement


class StatementReaderTest(unittest.TestCase):
    @patch("libs.tools.statement_reader.create_chat_model")
    def test_missing_structured_response_is_returned_as_none(self, create_model):
        structured_model = Mock()
        structured_model.invoke.return_value = None
        create_model.return_value.with_structured_output.return_value = structured_model
        config = LLMConfig(
            provider=OPENAI_COMPATIBLE,
            model="test-model",
            api_key="test-key",
            base_url="http://localhost:1234/v1",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "statement.png"
            image_path.write_bytes(b"image")

            response = read_statement(config, [str(image_path)])

        self.assertIsNone(response)
        structured_model.invoke.assert_called_once()


if __name__ == "__main__":
    unittest.main()
