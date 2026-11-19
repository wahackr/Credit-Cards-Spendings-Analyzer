import os

from langchain.messages import HumanMessage

from libs.llm.main import LLMConfig, create_chat_model
from libs.prompts.main import STATEMENT_TEXT_INSTRUCTIONS
from libs.states.statement import Statement

DEBUG_RESPONSE_ENV = "LLM_DEBUG_RESPONSE"
"""Set to a truthy value to print the raw structured response (dumps card data to the log)."""


def _debug_enabled() -> bool:
    return os.getenv(DEBUG_RESPONSE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


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
    response = structured_output_model.invoke([HumanMessage(content=content)])

    if response is not None and _debug_enabled():
        print("=" * 64)
        print(f"Structured LLM response ({config.provider} / {config.model}):")
        print(response.model_dump_json(indent=2))
        print("=" * 64)
    return response
