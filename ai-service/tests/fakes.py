from app.infrastructure.llm.base import LlmClient


class FakeLlmClient(LlmClient):
    def __init__(self, sql: str = "", respuestas: list[str] | None = None):
        self.respuesta = sql
        self.respuestas = list(respuestas) if respuestas else None
        self.excepcion: Exception | None = None
        self.llamadas: list[tuple[str, str]] = []

    async def generar_sql(self, system_prompt: str, pregunta: str) -> str:
        self.llamadas.append((system_prompt, pregunta))
        if self.excepcion is not None:
            raise self.excepcion
        if self.respuestas:
            return self.respuestas.pop(0)
        return self.respuesta