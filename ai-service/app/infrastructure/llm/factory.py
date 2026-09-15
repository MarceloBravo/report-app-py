from app.config import Settings
from app.infrastructure.llm.base import LlmClient


def crear_cliente(settings: Settings) -> LlmClient:
    proveedor = settings.llm_provider.strip().lower()
    if proveedor == "openai":
        from app.infrastructure.llm.openai_client import OpenAILLMClient

        return OpenAILLMClient(
            api_key=settings.openai_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
            max_tokens=settings.llm_max_tokens,
        )
    if proveedor == "anthropic":
        from app.infrastructure.llm.anthropic_client import AnthropicLLMClient

        return AnthropicLLMClient(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            timeout=settings.llm_timeout_seconds,
            max_tokens=settings.llm_max_tokens,
        )
    raise ValueError(f"proveedor LLM no soportado: {settings.llm_provider}")