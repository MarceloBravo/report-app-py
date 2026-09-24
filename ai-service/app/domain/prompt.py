from dataclasses import dataclass

from app.domain.esquema import EsquemaTenant, TablaEsquema

ROL_SISTEMA = (
    "Eres un generador de SQL de solo lectura. Dado un esquema de base de datos PostgreSQL 16, "
    "traduce la pregunta del usuario a una única sentencia SQL."
)

GUARDRAILS = [
    "Genera únicamente sentencias SELECT; está prohibido INSERT, UPDATE, DELETE y cualquier DDL.",
    "No uses punto y coma en ningún lugar de la consulta, ni siquiera al final.",
    "No incluyas comentarios (-- ni /* */).",
    "Sin saltos de línea ni el texto literal '\\n': toda la consulta en una sola línea.",
    "Utiliza SQL estándar de PostgreSQL 16.",
    "Responde únicamente con el SQL, sin explicaciones, sin markdown ni texto adicional.",
    "No envuelvas el SQL en bloques de código ni comillas invertidas (``` ni ```sql).",
    "Une las tablas recorriendo SIEMPRE las claves foráneas del esquema (FK -> tabla.columna); "
    "no omitas ningún JOIN necesario para resolver un filtro.",
    "Usa alias de tabla en todas ellas, aunque los nombres de columna no sean ambiguos.",
    "Usa EXCLUSIVAMENTE tablas y columnas listadas en el esquema: no inventes ni cambies ninguna.",
    "No derives nombres de tablas ni columnas a partir del texto de la pregunta del usuario.",
    "Toda tabla de FROM/JOIN debe figurar en el esquema: si no está, no existe.",
    "Ejemplo: con 'Notebooks' en la pregunta y el esquema con 'productos', usa 'productos'.",
    "El esquema indica cada clave foránea con la tabla y la columna a la que referencia: "
    "úsalas para unir las tablas, no inventes relaciones.",
    "Sólo en caso de no existir claves foráneas, relaciona las entidades de la pregunta "
    "con las tablas del esquema por su significado.",
    "Aplica cada filtro del usuario sobre la columna cuyo significado coincida con ese concepto, "
    "aunque esa columna esté en otra tabla.",
    "Si el atributo del filtro no está en la tabla principal, recorre las claves foráneas "
    "del esquema hasta encontrar la columna correcta y agrega el JOIN correspondiente.",
    "Ejemplo: 'Notebooks cuya marca sea Lenovo': si products.mark_id referencia marks.id y marks "
    "tiene la columna name, une products con marks y filtra m.name = 'Lenovo'.",
    "Nunca apliques un filtro a una columna solo por parecido de nombre: "
    "si el concepto vive en otra tabla, únela por su clave foránea.",
    "Combina SIEMPRE todos los filtros con AND, nunca con OR.",
    "Usa '=' para igualar valores, salvo que el usuario pida coincidencia parcial.",
    "Si el usuario pide no distinguir mayúsculas/minúsculas, usa ILIKE o "
    "LOWER(columna) = LOWER(valor); nunca uses LIKE sin normalizar.",
    "Para coincidencias parciales usa LIKE o ILIKE con '%' alrededor del valor "
    "(ejemplo: '%lenovo%').",
    "Si el esquema no permite responder, usa solo el texto exacto indicado abajo.",
    "No uses ninguna tabla o columna que no figure en el esquema.",
]

AVISO_TRUNCADO = (
    "ATENCION: el esquema fue truncado por límites del servicio; algunas tablas o columnas "
    "no fueron incluidas y no deben ser usadas en la consulta."
)

AVISO_PROMPT_TRUNCADO = "[prompt truncado por límite de tamaño del servicio]"

RESPUESTA_NO_SQL = "No se puede generar una consulta SQL con el esquema proporcionado."

REGLAS_REVISION = [
    "Verifica que cada filtro de la pregunta se aplique sobre la columna correcta "
    "según su significado.",
    "Si el atributo filtrado pertenece a otra tabla, une esa tabla mediante su clave foránea "
    "(FK -> tabla.columna) y corrige la columna del filtro.",
    "Ejemplo: filtrar por 'marca' exige unir la tabla de marcas por su FK y filtrar su "
    "columna name; nunca dejes el filtro sobre la columna homónima de la tabla principal.",
    "No omitas ningún JOIN necesario para resolver un filtro.",
    "Mantén un único SELECT: sin punto y coma, sin comentarios y sin markdown.",
    "Si la consulta ya es correcta, devuélvela exactamente igual.",
]


@dataclass(frozen=True)
class PromptMaestro:
    system: str
    pregunta: str
    esquemaTruncado: bool = False


def _destino_fk(columna) -> str:
    if not columna.columnaReferenciada:
        return columna.tablaReferenciada
    return f"{columna.tablaReferenciada}.{columna.columnaReferenciada}"


def _renderizar_columna(columna) -> str:
    flags = []
    if not columna.nullable:
        flags.append("NOT NULL")
    if columna.esPrimaryKey:
        flags.append("PK")
    if columna.esForeignKey and columna.tablaReferenciada:
        flags.append(f"FK -> {_destino_fk(columna)}")
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


def _renderizar_relaciones(
    esquema: EsquemaTenant, max_tablas: int, max_columnas: int
) -> tuple[str, bool]:
    lineas = []
    for tabla in esquema.tablas[:max_tablas]:
        for columna in tabla.columnas[:max_columnas]:
            if not columna.esForeignKey or not columna.tablaReferenciada:
                continue
            origen = columna.tabla or tabla.nombre
            lineas.append(f"  - {origen}.{columna.nombre} -> {_destino_fk(columna)}")
    return "\n".join(lineas), bool(lineas)


def _limitar_prompt_total(sistema: str, pregunta: str, max_chars: int) -> str:
    disponible = max_chars - len(pregunta)
    if disponible <= 0 or len(sistema) <= disponible:
        return sistema if disponible > 0 else ""
    presupuesto = disponible - len(AVISO_PROMPT_TRUNCADO) - 1
    if presupuesto <= 0:
        return AVISO_PROMPT_TRUNCADO
    recortado = sistema[:presupuesto]
    salto = recortado.rfind("\n")
    if salto != -1:
        recortado = recortado[:salto]
    return recortado.rstrip() + "\n" + AVISO_PROMPT_TRUNCADO


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
    frag_relaciones, hay_relaciones = _renderizar_relaciones(
        esquema, max_schema_tables, max_schema_columns
    )
    lineas = [
        ROL_SISTEMA,
        "",
        "Reglas obligatorias:",
        *GUARDRAILS,
        "",
        "Si no puedes responder, responde únicamente con este texto exacto:",
        RESPUESTA_NO_SQL,
        "",
        "Esquema de la base de datos:",
        frag_esquema,
    ]
    if hay_relaciones:
        lineas.extend(["", "Relaciones entre tablas (claves foráneas):", frag_relaciones])
    if esquema_truncado:
        lineas.append(AVISO_TRUNCADO)
    system = "\n".join(lineas)
    system = _limitar_prompt_total(system, pregunta, max_prompt_chars)
    return PromptMaestro(system=system, pregunta=pregunta, esquemaTruncado=esquema_truncado)


def construir_prompt_revision(
    esquema: EsquemaTenant,
    pregunta: str,
    sql: str,
    max_schema_tables: int = 50,
    max_schema_columns: int = 200,
) -> str:
    """Compone el prompt de una segunda pasada que revisa/corrige el SQL generado.

    Se le entrega al LLM el mismo esquema con sus claves foráneas, la pregunta
    original y el SQL borrador para que corrija JOINs y columnas de filtro.
    """
    frag_esquema, _ = _renderizar_esquema(esquema, max_schema_tables, max_schema_columns)
    frag_relaciones, hay_relaciones = _renderizar_relaciones(
        esquema, max_schema_tables, max_schema_columns
    )
    lineas = [
        "Eres un revisor de sentencias SQL. Revisa la consulta SQL generada para una pregunta "
        "en lenguaje natural usando el esquema de la base de datos y sus claves foráneas.",
        "",
        "Reglas obligatorias de revisión:",
        *REGLAS_REVISION,
        "",
        "Esquema de la base de datos:",
        frag_esquema,
    ]
    if hay_relaciones:
        lineas.extend(["", "Relaciones entre tablas (claves foráneas):", frag_relaciones])
    lineas.extend(["", "Pregunta del usuario:", pregunta, "", "SQL a revisar:", sql])
    return "\n".join(lineas)