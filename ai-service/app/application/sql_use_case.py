import time

from app.api.schemas import RequestSql, ResponseSql
from app.config import Settings
from app.domain.guardrails import validar_sql_generado
from app.domain.prompt import construir_prompt_maestro
from app.infrastructure.llm.base import LlmClient


class SqlUseCase:
    def __init__(self, llm_cliente: LlmClient, settings: Settings):
        self._llm = llm_cliente
        self._settings = settings

    async def generar(self, consulta: RequestSql) -> ResponseSql:
        inicio = time.monotonic()
        prompt = construir_prompt_maestro(
            consulta.esquema,
            consulta.preguntaUsuario,
            max_schema_tables=self._settings.max_schema_tables,
            max_schema_columns=self._settings.max_schema_columns,
            max_prompt_chars=self._settings.max_prompt_chars,
        )
        sql = await self._llm.generar_sql(prompt.system, prompt.pregunta)
        sql_valido = validar_sql_generado(sql)
        return ResponseSql(
            tenantId=consulta.tenantId,
            querySql=sql_valido,
            exitosa=True,
            tiempoMs=max(0, int((time.monotonic() - inicio) * 1000)),
        )