import os
from dataclasses import dataclass
from typing import Mapping

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

GEMINI = "gemini"
OPENAI_COMPATIBLE = "openai-compatible"
SUPPORTED_PROVIDERS = (GEMINI, OPENAI_COMPATIBLE)


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
) -> LLMConfig:
    """Load and validate provider-specific configuration."""
    env = os.environ if environ is None else environ
    selected_provider = (provider or env.get("LLM_PROVIDER", GEMINI)).strip().lower()

    if selected_provider not in SUPPORTED_PROVIDERS:
        choices = ", ".join(SUPPORTED_PROVIDERS)
        raise ValueError(f"Unsupported LLM_PROVIDER '{selected_provider}'. Choose one of: {choices}.")

    if selected_provider == GEMINI:
        api_key = env.get("GEMINI_API_KEY", "").strip()
        selected_model = (model or env.get("GEMINI_MODEL", "gemini-3-flash-preview")).strip()
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini.")
        if not selected_model:
            raise ValueError("GEMINI_MODEL must not be empty when LLM_PROVIDER=gemini.")
        return LLMConfig(selected_provider, selected_model, api_key)

    base_url = env.get("OPENAI_BASE_URL", "").strip()
    api_key = env.get("OPENAI_API_KEY", "not-required").strip()
    selected_model = (model or env.get("OPENAI_MODEL", "")).strip()
    if not base_url:
        raise ValueError(
            "OPENAI_BASE_URL is required when LLM_PROVIDER=openai-compatible."
        )
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
    if config.provider == GEMINI:
        return ChatGoogleGenerativeAI(api_key=config.api_key, model=config.model)
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
