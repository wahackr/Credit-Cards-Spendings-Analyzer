import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Repo-root .env supplies defaults; explicit environment variables take precedence.
load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)

OPENAI_COMPATIBLE = "openai-compatible"
SUPPORTED_PROVIDERS = (OPENAI_COMPATIBLE,)
REMOVED_PROVIDERS = {
    "gemini": (
        "Gemini support was removed when statements switched to extracted text; "
        "set LLM_PROVIDER=openai-compatible with OPENAI_BASE_URL and OPENAI_MODEL."
    )
}


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str
    base_url: str | None = None
    thinking: bool | None = None
    max_output_tokens: int | None = None


def _optional_bool(env: Mapping[str, str], name: str) -> bool | None:
    value = env.get(name)
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false.")


def _optional_positive_int(env: Mapping[str, str], name: str) -> int | None:
    value = env.get(name)
    if value is None or not value.strip():
        return None
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer.") from error
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return parsed


def load_llm_config(
    environ: Mapping[str, str] | None = None,
    *,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> LLMConfig:
    """Load and validate provider-specific configuration."""
    env = os.environ if environ is None else environ
    selected_provider = (provider or env.get("LLM_PROVIDER", OPENAI_COMPATIBLE)).strip().lower()

    if selected_provider in REMOVED_PROVIDERS:
        raise ValueError(REMOVED_PROVIDERS[selected_provider])

    if selected_provider not in SUPPORTED_PROVIDERS:
        choices = ", ".join(SUPPORTED_PROVIDERS)
        raise ValueError(f"Unsupported LLM_PROVIDER '{selected_provider}'. Choose one of: {choices}.")

    base_url = (env.get("OPENAI_BASE_URL", "") if base_url is None else base_url).strip()
    api_key = env.get("OPENAI_API_KEY", "not-required").strip()
    selected_model = (model or env.get("OPENAI_MODEL", "")).strip()
    if not base_url:
        raise ValueError(
            "OPENAI_BASE_URL is required when LLM_PROVIDER=openai-compatible."
        )
    try:
        endpoint = urlsplit(base_url)
        valid_endpoint = endpoint.scheme in {"http", "https"} and bool(endpoint.hostname)
        endpoint.port  # Validate the port when present.
    except ValueError:
        valid_endpoint = False
    if not valid_endpoint:
        raise ValueError("OpenAI endpoint must be an absolute http:// or https:// URL.")
    if not selected_model:
        raise ValueError(
            "OPENAI_MODEL is required when LLM_PROVIDER=openai-compatible."
        )
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY must not be empty; use 'not-required' for servers that ignore it."
        )
    return LLMConfig(
        selected_provider,
        selected_model,
        api_key,
        base_url,
        thinking=_optional_bool(env, "OPENAI_THINKING"),
        max_output_tokens=_optional_positive_int(env, "OPENAI_MAX_OUTPUT_TOKENS"),
    )


def configured_providers(
    environ: Mapping[str, str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Return providers with valid environment configuration and validation errors."""
    env = os.environ if environ is None else environ
    available = []
    errors = {}
    for provider in SUPPORTED_PROVIDERS:
        try:
            load_llm_config(env, provider=provider)
        except ValueError as error:
            errors[provider] = str(error)
        else:
            available.append(provider)
    return available, errors


def create_chat_model(config: LLMConfig):
    if config.provider == OPENAI_COMPATIBLE:
        extra_body = (
            {"think": config.thinking} if config.thinking is not None else None
        )
        return ChatOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            temperature=0,
            max_tokens=config.max_output_tokens,
            extra_body=extra_body,
        )
    raise ValueError(f"Unsupported LLM provider: {config.provider}")
