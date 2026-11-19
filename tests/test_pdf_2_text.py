import unittest

from libs.tools.pdf_2_text import StatementTextError, extract_statement_text
from pdf_fixture import ROWS, scanned_pdf, statement_pdf


class PdfToTextTests(unittest.TestCase):
    def test_amounts_and_merchants_survive_extraction(self):
        text = extract_statement_text(statement_pdf(), filename="bank-202611/statement.pdf")

        self.assertIn("1,198.00", text.markdown)
        self.assertIn("YF LIFE INSURANCE PREMIUM", text.markdown)
        self.assertGreaterEqual(text.char_count, 200)

    def test_table_columns_are_rebuilt_as_table_rows(self):
        text = extract_statement_text(statement_pdf())

        self.assertGreaterEqual(text.table_rows, len(ROWS))
        self.assertGreaterEqual(text.amount_tokens, 2 * len(ROWS))

    def test_scanned_statement_is_rejected_before_any_llm_call(self):
        with self.assertRaises(StatementTextError) as raised:
            extract_statement_text(scanned_pdf(), filename="scan.pdf")

        self.assertIn("scan.pdf", str(raised.exception))
        self.assertIn("text layer", str(raised.exception))

    def test_unreadable_file_is_reported_with_its_name(self):
        with self.assertRaises(StatementTextError) as raised:
            extract_statement_text(b"definitely not a pdf", filename="junk.pdf")

        self.assertIn("junk.pdf", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
