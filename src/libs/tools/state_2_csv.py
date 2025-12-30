import csv
from io import StringIO

from libs.states.main import Statement


def statement_to_csv(statement: Statement) -> str:
    """
    Convert transactions in a Statement object to CSV format.

    Args:
        statement: Statement object containing transactions

    Returns:
        CSV formatted string with header and transaction rows
    """
    output = StringIO()
    writer = csv.writer(output)

    # Write header
    # writer.writerow(["date", "transaction_name", "amount", "category"])

    # Write transaction rows
    for transaction in statement.transactions:
        writer.writerow([
            transaction.date,
            transaction.transaction_name,
            transaction.amount,
            transaction.category,
            transaction.account,
            transaction.card_name
        ])

    return output.getvalue()
