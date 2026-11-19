"""CLI batch entry point: analyze every PDF under ./statements and print one CSV."""

import os
from pathlib import Path

from libs.llm.main import load_llm_config
from libs.tools.pdf_2_text import get_pdf_files
from libs.tools.statement_processor import (
    StatementUpload,
    get_max_concurrent_statements,
    process_statements_concurrently,
)
from libs.tools.statement_results import is_populated_statement

CSV_HEADER = "date,transaction_name,amount,category,account,card_name\n"
STATEMENTS_FOLDER = "statements"


def main() -> int:
    try:
        llm_config = load_llm_config()
        max_workers = get_max_concurrent_statements()
    except ValueError as error:
        raise SystemExit(f"Configuration error: {error}") from error

    pdf_folder = f"{os.getcwd()}/{STATEMENTS_FOLDER}"
    pdf_files = sorted(get_pdf_files(pdf_folder))
    if not pdf_files:
        raise SystemExit(f"No PDF statements found in {pdf_folder}")

    print(f"Found {len(pdf_files)} PDF statement(s), analyzing with {max_workers} worker(s).")

    uploads = []
    for index, pdf_path in enumerate(pdf_files):
        uploads.append(StatementUpload(index, pdf_path, Path(pdf_path).read_bytes()))

    results = sorted(
        process_statements_concurrently(
            uploads,
            llm_config,
            max_workers=max_workers,
            on_progress=lambda event: print(f"{event.filename}: {event.stage} {event.detail}".rstrip()),
        ),
        key=lambda result: result.index,
    )

    statement_rows = CSV_HEADER
    failures = 0
    for result in results:
        if result.error is not None:
            failures += 1
            print(f"FAILED {result.filename}: {result.error}")
            continue
        if not is_populated_statement(result.statement):
            print(f"EMPTY {result.filename}: no transactions found")
            continue
        statement = result.statement
        print(
            f"DONE {result.filename}: {statement.number_of_transactions} transactions, "
            f"total {statement.total_spending}"
        )
        statement_rows += result.csv_rows

    print("CSV Output:")
    print(statement_rows)
    return 1 if failures == len(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
