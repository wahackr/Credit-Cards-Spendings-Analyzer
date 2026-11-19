import os
import sys

from langchain.messages import HumanMessage

from libs.llm.main import LLMConfig, create_chat_model
from libs.prompts.main import STATEMENT_TEXT_INSTRUCTIONS
from libs.states.statement import Statement

DEBUG_ENV = "LLM_DEBUG"
"""Set to a truthy value to print the full text sent to the LLM and its parsed response.

Both dumps contain raw card data, so this stays off by default. Output goes to stderr to
keep the CLI's CSV stdout usable when redirected to a file.
"""


def _debug_enabled() -> bool:
    return os.getenv(DEBUG_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _log_debug(config: LLMConfig, heading: str, body: str) -> None:
    print(
        f"{'=' * 64}\n"
        f"{heading} ({config.provider} / {config.model}):\n"
        f"{body}\n"
        f"{'=' * 64}",
        file=sys.stderr,
    )


def read_statement(
    config: LLMConfig,
    statement_text: str,
) -> Statement | None:
    """Read statement Markdown text, returning None when no structured call is made."""
    if not statement_text.strip():
        raise ValueError("At least one statement text is required.")

    model = create_chat_model(config)
    structured_output_model = model.with_structured_output(Statement)

    content = f"{STATEMENT_TEXT_INSTRUCTIONS}\n\nStatement text:\n\n{statement_text}"
    debug = _debug_enabled()
    if debug:
        _log_debug(config, f"LLM request — {len(content):,} characters", content)

    response = structured_output_model.invoke([HumanMessage(content=content)])

    if debug:
        _log_debug(
            config,
            "LLM response",
            response.model_dump_json(indent=2)
            if response is not None
            else "<no structured response>",
        )
    return response
