from abc import ABC, abstractmethod


class LlmClient(ABC):
    @abstractmethod
    async def generar_sql(self, system_prompt: str, pregunta: str) -> str:
        """Devuelve el SQL generado por el LLM para la pregunta dada."""
        raise NotImplementedError