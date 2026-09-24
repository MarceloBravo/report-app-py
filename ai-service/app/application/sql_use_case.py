import time

from app.api.schemas import RequestSql, ResponseSql
from app.config import Settings
from app.domain.errors import IaNoDevolvioSqlError
from app.domain.guardrails import validar_sql_generado
from app.domain.prompt import construir_prompt_maestro, construir_prompt_revision
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
        sql = validar_sql_generado(sql, consulta.esquema)
        if self._settings.llm_revisar_fk and consulta.esquema.tiene_relaciones:
            sql = await self._revisar_sql(consulta, sql)
        return ResponseSql(
            tenantId=consulta.tenantId,
            querySql=sql,
            exitosa=True,
            tiempoMs=max(0, int((time.monotonic() - inicio) * 1000)),
        )

    async def _revisar_sql(self, consulta: RequestSql, sql_original: str) -> str:
        """Segunda pasada: corrige JOINs faltantes de claves foráneas.

        Si la revisión devuelve un SQL que no supera los guardrails, se conserva
        el SQL original (que ya fue validado) en lugar de propagar un error.
        """
        prompt = construir_prompt_revision(
            consulta.esquema,
            consulta.preguntaUsuario,
            sql_original,
            max_schema_tables=self._settings.max_schema_tables,
            max_schema_columns=self._settings.max_schema_columns,
        )
        sql_revisado = await self._llm.generar_sql(prompt, sql_original)
        try:
            return validar_sql_generado(sql_revisado, consulta.esquema)
        except IaNoDevolvioSqlError:
            return sql_original