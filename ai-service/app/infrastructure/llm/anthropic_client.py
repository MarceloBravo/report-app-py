from app.domain.errors import ProveedorIaIndisponibleError
from app.infrastructure.llm.base import LlmClient


class AnthropicLLMClient(LlmClient):
    def __init__(self, api_key: str, model: str, timeout: float, max_tokens: int):
        from anthropic import AsyncAnthropic

        self._model = model
        self._max_tokens = max_tokens
        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout)

    async def generar_sql(self, system_prompt: str, pregunta: str) -> str:
        try:
            mensaje = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=0,
                system=system_prompt,
                messages=[{"role": "user", "content": pregunta}],
            )
        except Exception as error:
            raise ProveedorIaIndisponibleError(f"error del proveedor Anthropic: {error}") from error
        return "".join(bloque.text for bloque in mensaje.content if bloque.type == "text")