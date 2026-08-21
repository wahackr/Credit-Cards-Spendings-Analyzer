import unittest

from libs.states.statement import Statement, Transaction
from libs.tools.statement_results import (
    is_populated_statement,
    partition_statement_responses,
)


def make_statement(*transactions: Transaction) -> Statement:
    return Statement(
        transactions=list(transactions),
        card_name="Test Card",
        total_spending=sum(transaction.amount for transaction in transactions),
        number_of_transactions=len(transactions),
        due_date="2026-08-31",
    )


class StatementResultsTest(unittest.TestCase):
    def test_valid_statement_with_no_transactions_is_empty(self):
        self.assertFalse(is_populated_statement(make_statement()))

    def test_none_response_is_empty(self):
        self.assertFalse(is_populated_statement(None))

    def test_malformed_empty_response_is_empty(self):
        self.assertFalse(is_populated_statement({}))

    def test_mixed_batch_preserves_successful_statements(self):
        transaction = Transaction(
            date="2026-08-01",
            transaction_name="Merchant",
            amount=42,
            category="Others",
            account="Personal",
            card_name="Test Card",
        )
        successful = make_statement(transaction)

        populated, empty_files = partition_statement_responses(
            [
                ("first.pdf", successful),
                ("empty.pdf", None),
                ("last.pdf", successful),
            ]
        )

        self.assertEqual([name for name, _ in populated], ["first.pdf", "last.pdf"])
        self.assertEqual(empty_files, ["empty.pdf"])

    def test_all_empty_batch_has_no_populated_statements(self):
        populated, empty_files = partition_statement_responses(
            [("one.pdf", make_statement()), ("two.pdf", {})]
        )

        self.assertEqual(populated, [])
        self.assertEqual(empty_files, ["one.pdf", "two.pdf"])


if __name__ == "__main__":
    unittest.main()
