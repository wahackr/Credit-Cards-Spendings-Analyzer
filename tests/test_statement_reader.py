import unittest
from unittest.mock import Mock, patch

from libs.llm.main import LLMConfig, OPENAI_COMPATIBLE
from libs.tools.statement_reader import read_statement


class StatementReaderTest(unittest.TestCase):
    def _config(self) -> LLMConfig:
        return LLMConfig(
            provider=OPENAI_COMPATIBLE,
            model="test-model",
            api_key="test-key",
            base_url="http://localhost:1234/v1",
        )

    @patch("libs.tools.statement_reader.create_chat_model")
    def test_missing_structured_response_is_returned_as_none(self, create_model):
        structured_model = Mock()
        structured_model.invoke.return_value = None
        create_model.return_value.with_structured_output.return_value = structured_model

        response = read_statement(self._config(), "| Date | Amount |\n| 02/11 | 1,198.00 |")

        self.assertIsNone(response)
        structured_model.invoke.assert_called_once()

    @patch("libs.tools.statement_reader.create_chat_model")
    def test_statement_text_is_sent_as_plain_message_content(self, create_model):
        structured_model = Mock()
        structured_model.invoke.return_value = None
        create_model.return_value.with_structured_output.return_value = structured_model

        read_statement(self._config(), "| 02/11 | APPLE | 1,198.00 |")

        message = structured_model.invoke.call_args.args[0][0]
        self.assertTrue(
            message.content.strip().startswith("Analyze the credit card statement text")
        )
        self.assertIn("| 02/11 | APPLE | 1,198.00 |", message.content)
        self.assertNotIn("image", message.content.lower())

    def test_empty_statement_text_is_rejected(self):
        with self.assertRaises(ValueError):
            read_statement(self._config(), "   ")


if __name__ == "__main__":
    unittest.main()
