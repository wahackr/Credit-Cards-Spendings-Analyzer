import io
import os
import ssl
import unittest
from contextlib import redirect_stderr
from unittest.mock import Mock, patch

from libs.llm.main import LLMConfig, OPENAI_COMPATIBLE
from libs.states.statement import Statement, Transaction
from libs.tools.statement_reader import read_statement


class StatementReaderTest(unittest.TestCase):
    def _config(self) -> LLMConfig:
        return LLMConfig(
            provider=OPENAI_COMPATIBLE,
            model="test-model",
            api_key="test-key",
            base_url="http://localhost:1234/v1",
        )

    def _statement(self) -> Statement:
        return Statement(
            transactions=[
                Transaction(
                    date="2026-11-02",
                    transaction_name="APPLE PAYSUBSCR PSE *IPHONE",
                    amount=1198.00,
                    category="Shopping",
                    account="Personal",
                    card_name="World Card",
                )
            ],
            card_name="World Card",
            total_spending=1198.00,
            number_of_transactions=1,
            due_date="2026-12-01",
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

    @patch("libs.tools.statement_reader.create_chat_model")
    def test_debug_flag_prints_payload_and_response(self, create_model):
        structured_model = Mock()
        structured_model.invoke.return_value = self._statement()
        create_model.return_value.with_structured_output.return_value = structured_model
        printed = io.StringIO()

        with patch.dict(os.environ, {"LLM_DEBUG": "1"}), redirect_stderr(printed):
            read_statement(self._config(), "| 02/11 | APPLE | 1,198.00 |")

        output = printed.getvalue()
        self.assertIn("LLM request", output)
        self.assertIn("| 02/11 | APPLE | 1,198.00 |", output)
        self.assertIn("LLM response", output)
        self.assertIn("APPLE PAYSUBSCR PSE *IPHONE", output)

    @patch("libs.tools.statement_reader.create_chat_model")
    def test_payload_is_printed_before_the_request_so_a_failed_attempt_is_visible(self, create_model):
        structured_model = Mock()
        structured_model.invoke.side_effect = ssl.SSLError("Server disconnected")
        create_model.return_value.with_structured_output.return_value = structured_model
        printed = io.StringIO()

        with patch.dict(os.environ, {"LLM_DEBUG": "1"}), redirect_stderr(printed):
            with self.assertRaises(ssl.SSLError):
                read_statement(self._config(), "| 02/11 | APPLE | 1,198.00 |")

        self.assertIn("| 02/11 | APPLE | 1,198.00 |", printed.getvalue())
        self.assertNotIn("LLM response", printed.getvalue())

    @patch("libs.tools.statement_reader.create_chat_model")
    def test_debug_output_is_off_by_default(self, create_model):
        structured_model = Mock()
        structured_model.invoke.return_value = self._statement()
        create_model.return_value.with_structured_output.return_value = structured_model
        printed = io.StringIO()

        with patch.dict(os.environ, {}, clear=True), redirect_stderr(printed):
            read_statement(self._config(), "| 02/11 | APPLE | 1,198.00 |")

        self.assertEqual(printed.getvalue(), "")

    def test_empty_statement_text_is_rejected(self):
        with self.assertRaises(ValueError):
            read_statement(self._config(), "   ")


if __name__ == "__main__":
    unittest.main()
