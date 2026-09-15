from dataclasses import dataclass

from app.domain.esquema import EsquemaTenant, TablaEsquema

ROL_SISTEMA = (
    "Eres un generador de SQL de solo lectura. Dado un esquema de base de datos PostgreSQL 16, "
    "traduce la pregunta del usuario a una única sentencia SQL."
)

GUARDRAILS = [
    "Genera únicamente sentencias SELECT; está prohibido INSERT, UPDATE, DELETE y cualquier DDL.",
    "No termines con punto y coma; no incluyas comentarios (-- ni /* */).",
    "Utiliza SQL estándar de PostgreSQL 16.",
    "Responde únicamente con el SQL, sin explicaciones, sin markdown ni texto adicional.",
]

AVISO_TRUNCADO = (
    "ATENCION: el esquema fue truncado por límites del servicio; algunas tablas o columnas "
    "no fueron incluidas y no deben ser usadas en la consulta."
)

AVISO_PROMPT_TRUNCADO = "[prompt truncado por límite de tamaño del servicio]"


@dataclass(frozen=True)
class PromptMaestro:
    system: str
    pregunta: str
    esquemaTruncado: bool = False


def _renderizar_columna(columna) -> str:
    flags = []
    if not columna.nullable:
        flags.append("NOT NULL")
    if columna.esPrimaryKey:
        flags.append("PK")
    sufijo = f" ({', '.join(flags)})" if flags else ""
    return f"    - {columna.nombre}: {columna.tipoDato}{sufijo}"


def _renderizar_tabla(tabla: TablaEsquema, max_columnas: int) -> tuple[str, bool]:
    columnas_a_mostrar = tabla.columnas[:max_columnas]
    lineas = [f"  - {tabla.nombre} (tabla)"]
    lineas.extend(_renderizar_columna(c) for c in columnas_a_mostrar)
    return "\n".join(lineas), len(tabla.columnas) > max_columnas


def _renderizar_esquema(
    esquema: EsquemaTenant, max_tablas: int, max_columnas: int
) -> tuple[str, bool]:
    tablas_a_mostrar = esquema.tablas[:max_tablas]
    partes = [_renderizar_tabla(t, max_columnas) for t in tablas_a_mostrar]
    lineas = [parte for parte, _ in partes]
    truncado = len(esquema.tablas) > max_tablas or any(t for _, t in partes)
    return "\n".join(lineas), truncado


def _limitar_prompt_total(sistema: str, pregunta: str, max_chars: int) -> str:
    disponible = max_chars - len(pregunta)
    if disponible <= 0 or len(sistema) <= disponible:
        return sistema if disponible > 0 else ""
    return sistema[: disponible - len(AVISO_PROMPT_TRUNCADO)] + AVISO_PROMPT_TRUNCADO


def construir_prompt_maestro(
    esquema: EsquemaTenant,
    pregunta: str,
    max_schema_tables: int = 50,
    max_schema_columns: int = 200,
    max_prompt_chars: int = 8000,
) -> PromptMaestro:
    frag_esquema, esquema_truncado = _renderizar_esquema(
        esquema, max_schema_tables, max_schema_columns
    )
    lineas = [
        ROL_SISTEMA,
        "",
        "Reglas obligatorias:",
        *GUARDRAILS,
        "",
        "Esquema de la base de datos:",
        frag_esquema,
    ]
    if esquema_truncado:
        lineas.append(AVISO_TRUNCADO)
    system = "\n".join(lineas)
    system = _limitar_prompt_total(system, pregunta, max_prompt_chars)
    return PromptMaestro(system=system, pregunta=pregunta, esquemaTruncado=esquema_truncado)