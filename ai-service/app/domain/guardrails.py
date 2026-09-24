import re

from app.domain.errors import IaNoDevolvioSqlError
from app.domain.esquema import EsquemaTenant

_BLOQUE_MARKDOWN = re.compile(r"^```[A-Za-z0-9_+\-]*\r?\n(?P<sql>.*?)```\s*$", re.DOTALL)
_REFERENCIA_TABLA = re.compile(r"\b(?:FROM|JOIN)\s+([\"\w.]+)", re.IGNORECASE)
_LITERAL_CADENA = re.compile(r"'([^']|'')*'")
_DEFINICION_CTE = re.compile(r"\b([\w.]+)\s+AS\s*\(", re.IGNORECASE)


def _extraer_sql_base(sql: str) -> str:
    sql_limpio = (sql or "").strip()
    coincidencia = _BLOQUE_MARKDOWN.match(sql_limpio)
    if coincidencia:
        return coincidencia.group("sql").strip()
    return sql_limpio


def _una_sola_linea(sql: str) -> str:
    sql = re.sub(r"\\r\\n|\\r|\\n|\\t", " ", sql)
    return re.sub(r"\s+", " ", sql).strip()


def _quitar_literales(sql: str) -> str:
    return _LITERAL_CADENA.sub(" ", sql)


def _nombres_cte(sql: str) -> set[str]:
    return {
        nombre.strip('"').split(".")[-1].lower()
        for nombre in _DEFINICION_CTE.findall(_quitar_literales(sql))
    }


def _tablas_referenciadas(sql: str) -> list[str]:
    tablas: list[str] = []
    for referencia in _REFERENCIA_TABLA.findall(sql):
        nombre = referencia.strip('"').split(".")[-1]
        if nombre and not any(t.lower() == nombre.lower() for t in tablas):
            tablas.append(nombre)
    return tablas


def _validar_tablas(sql: str, esquema: EsquemaTenant | None) -> None:
    if esquema is None:
        return
    sql_sin_literales = _quitar_literales(sql)
    permitidas = {tabla.nombre.lower() for tabla in esquema.tablas}
    permitidas |= _nombres_cte(sql_sin_literales)
    for tabla in _tablas_referenciadas(sql_sin_literales):
        if tabla.lower() not in permitidas:
            raise IaNoDevolvioSqlError(
                f"la respuesta del proveedor de IA hace referencia a la tabla "
                f"'{tabla}', que no existe en el esquema proporcionado"
            )


def validar_sql_generado(sql: str, esquema: EsquemaTenant | None = None) -> str:
    """Valida el SQL devuelto por el LLM contra los guardrails.

    Normaliza el SQL a una única línea (elimina saltos de línea reales y
    las secuencias literales '\\n', '\\r') y comprueba que las tablas
    referenciadas existan en el esquema. Lanza `IaNoDevolvioSqlError` si
    no cumple las reglas.
    """
    sql_limpio = _extraer_sql_base(sql)
    sql_limpio = _una_sola_linea(sql_limpio)
    sql_limpio = sql_limpio.rstrip(";").rstrip()
    if not sql_limpio:
        raise IaNoDevolvioSqlError("el proveedor de IA devolvió una respuesta vacía")
    if not re.match(r"(?:with\b.*\bselect\b|select\b)", sql_limpio, re.IGNORECASE):
        raise IaNoDevolvioSqlError("la respuesta del proveedor de IA no es una sentencia SELECT")
    if ";" in sql_limpio:
        raise IaNoDevolvioSqlError("la respuesta del proveedor de IA contiene un punto y coma")
    if "--" in sql_limpio or "/*" in sql_limpio:
        raise IaNoDevolvioSqlError("la respuesta del proveedor de IA contiene comentarios SQL")
    _validar_tablas(sql_limpio, esquema)
    return sql_limpio