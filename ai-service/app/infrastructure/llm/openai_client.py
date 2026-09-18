from openai import AsyncOpenAI

from app.domain.errors import ProveedorIaIndisponibleError
from app.infrastructure.llm.base import LlmClient


class OpenAILLMClient(LlmClient):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float,
        max_tokens: int,
        base_url: str | None = None,
    ):
        self._model = model
        self._max_tokens = max_tokens
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout, base_url=base_url)

    async def generar_sql(self, system_prompt: str, pregunta: str) -> str:
        try:
            respuesta = await self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": pregunta},
                ],
            )
        except Exception as error:
            raise ProveedorIaIndisponibleError(f"error del proveedor OpenAI: {error}") from error
        return respuesta.choices[0].message.content or ""