import re

from app.domain.errors import IaNoDevolvioSqlError

_BLOQUE_MARKDOWN = re.compile(r"^```[A-Za-z0-9_+\-]*\r?\n(?P<sql>.*?)```\s*$", re.DOTALL)


def _extraer_sql_base(sql: str) -> str:
    sql_limpio = (sql or "").strip()
    coincidencia = _BLOQUE_MARKDOWN.match(sql_limpio)
    if coincidencia:
        return coincidencia.group("sql").strip()
    return sql_limpio


def validar_sql_generado(sql: str) -> str:
    """Valida el SQL devuelto por el LLM contra los guardrails.

    Devuelve el SQL normalizado (sin espacios de los extremos) o lanza
    `IaNoDevolvioSqlError` si no cumple las reglas.
    """
    sql_limpio = _extraer_sql_base(sql)
    sql_limpio = sql_limpio.rstrip(";").rstrip()
    if not sql_limpio:
        raise IaNoDevolvioSqlError("el proveedor de IA devolvió una respuesta vacía")
    if not sql_limpio.lower().startswith("select"):
        raise IaNoDevolvioSqlError("la respuesta del proveedor de IA no es una sentencia SELECT")
    if ";" in sql_limpio:
        raise IaNoDevolvioSqlError("la respuesta del proveedor de IA contiene un punto y coma")
    if "--" in sql_limpio or "/*" in sql_limpio:
        raise IaNoDevolvioSqlError("la respuesta del proveedor de IA contiene comentarios SQL")
    return sql_limpio