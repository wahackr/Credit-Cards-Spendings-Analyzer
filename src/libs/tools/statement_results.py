from collections.abc import Iterable
from typing import TypeGuard

from libs.states.main import Statement


def is_populated_statement(response: object) -> TypeGuard[Statement]:
    """Return whether a structured response contains displayable transactions."""
    return isinstance(response, Statement) and bool(response.transactions)


def partition_statement_responses(
    responses: Iterable[tuple[str, object]],
) -> tuple[list[tuple[str, Statement]], list[str]]:
    """Split named responses into populated statements and empty filenames."""
    populated = []
    empty_files = []

    for filename, response in responses:
        if is_populated_statement(response):
            populated.append((filename, response))
        else:
            empty_files.append(filename)

    return populated, empty_files
