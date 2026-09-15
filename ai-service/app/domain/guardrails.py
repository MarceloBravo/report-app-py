from app.domain.errors import IaNoDevolvioSqlError


def validar_sql_generado(sql: str) -> str:
    """Valida el SQL devuelto por el LLM contra los guardrails.

    Devuelve el SQL normalizado (sin espacios de los extremos) o lanza
    `IaNoDevolvioSqlError` si no cumple las reglas.
    """
    sql_limpio = (sql or "").strip()
    if not sql_limpio:
        raise IaNoDevolvioSqlError("el proveedor de IA devolvió una respuesta vacía")
    if not sql_limpio.lower().startswith("select"):
        raise IaNoDevolvioSqlError("la respuesta del proveedor de IA no es una sentencia SELECT")
    if ";" in sql_limpio:
        raise IaNoDevolvioSqlError("la respuesta del proveedor de IA contiene un punto y coma")
    if "--" in sql_limpio or "/*" in sql_limpio:
        raise IaNoDevolvioSqlError("la respuesta del proveedor de IA contiene comentarios SQL")
    return sql_limpio