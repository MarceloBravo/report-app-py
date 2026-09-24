from app.domain.esquema import EsquemaTenant
from app.domain.prompt import (
    AVISO_PROMPT_TRUNCADO,
    construir_prompt_maestro,
    construir_prompt_revision,
)


def _esquema() -> EsquemaTenant:
    return EsquemaTenant.model_validate(
        {
            "tablas": [
                {
                    "nombre": "ventas",
                    "columnas": [
                        {"nombre": "id", "tipoDato": "uuid", "esPrimaryKey": True},
                        {"nombre": "monto", "tipoDato": "numeric", "nullable": False},
                        {"nombre": "fecha", "tipoDato": "timestamp", "nullable": False},
                    ],
                }
            ]
        }
    )


def test_prompt_incluye_esquema():
    prompt = construir_prompt_maestro(_esquema(), "¿Cuántas ventas por mes?")
    assert "ventas" in prompt.system
    assert "monto: numeric" in prompt.system
    assert "fecha: timestamp" in prompt.system


def _esquema_con_relacion() -> EsquemaTenant:
    return EsquemaTenant.model_validate(
        {
            "tablas": [
                {
                    "nombre": "ventas",
                    "columnas": [
                        {"nombre": "id", "tipoDato": "uuid", "esPrimaryKey": True},
                        {
                            "nombre": "cliente_id",
                            "tipoDato": "uuid",
                            "nullable": False,
                            "esForeignKey": True,
                            "tablaReferenciada": "clientes",
                            "columnaReferenciada": "id",
                        },
                    ],
                },
                {
                    "nombre": "clientes",
                    "columnas": [
                        {"nombre": "id", "tipoDato": "uuid", "esPrimaryKey": True},
                    ],
                },
            ]
        }
    )


def test_prompt_incluye_relaciones_entre_tablas():
    prompt = construir_prompt_maestro(
        _esquema_con_relacion(), "¿Cuántas ventas hubo por cliente?"
    )
    assert "cliente_id: uuid (NOT NULL, FK -> clientes.id)" in prompt.system
    assert "Relaciones entre tablas (claves foráneas):" in prompt.system
    assert "ventas.cliente_id -> clientes.id" in prompt.system


def test_prompt_sin_relaciones_no_incluye_seccion():
    prompt = construir_prompt_maestro(_esquema(), "¿Cuántas ventas por mes?")
    assert "Relaciones entre tablas" not in prompt.system


def _esquema_catalogo() -> EsquemaTenant:
    return EsquemaTenant.model_validate(
        {
            "tablas": [
                {
                    "nombre": "products",
                    "columnas": [
                        {"nombre": "id", "tipoDato": "uuid", "esPrimaryKey": True},
                        {"nombre": "name", "tipoDato": "varchar", "nullable": False},
                        {
                            "nombre": "mark_id",
                            "tipoDato": "uuid",
                            "esForeignKey": True,
                            "tablaReferenciada": "marks",
                            "columnaReferenciada": "id",
                        },
                    ],
                },
                {
                    "nombre": "marks",
                    "columnas": [
                        {"nombre": "id", "tipoDato": "uuid", "esPrimaryKey": True},
                        {"nombre": "name", "tipoDato": "varchar", "nullable": False},
                    ],
                },
            ]
        }
    )


def test_prompt_envia_fk_de_marca_al_llm():
    prompt = construir_prompt_maestro(
        _esquema_catalogo(), "Notebooks cuya marca sea Lenovo"
    )
    assert "mark_id: uuid (FK -> marks.id)" in prompt.system
    assert "products.mark_id -> marks.id" in prompt.system
    assert "marca sea Lenovo" in prompt.system


def test_prompt_revision_incluye_esquema_pregunta_y_sql():
    sql = "SELECT * FROM ventas WHERE ventas.nombre LIKE 'X%'"
    prompt = construir_prompt_revision(
        _esquema_con_relacion(), pregunta="¿Cuántas ventas por cliente?", sql=sql
    )
    assert "SQL a revisar" in prompt
    assert sql in prompt
    assert "Pregunta del usuario" in prompt
    assert "¿Cuántas ventas por cliente?" in prompt
    assert "ventas.cliente_id -> clientes.id" in prompt
    assert "clave foránea" in prompt


def test_prompt_incluye_guardrails():
    prompt = construir_prompt_maestro(_esquema(), "¿Cuántas ventas por mes?")
    assert "sentencias SELECT" in prompt.system
    assert "prohibido INSERT" in prompt.system
    assert "sin explicaciones" in prompt.system


def test_prompt_conserva_pregunta():
    pregunta = "¿Cuántas ventas hubo por mes en 2025?"
    prompt = construir_prompt_maestro(_esquema(), pregunta)
    assert prompt.pregunta == pregunta


def test_esquema_con_mas_tablas_se_trunca():
    esquema = _esquema()
    esquema.tablas.append(
        _esquema().tablas[0].model_copy(update={"nombre": "clientes"}),
    )
    prompt = construir_prompt_maestro(esquema, "consulta", max_schema_tables=1)
    assert prompt.esquemaTruncado is True
    assert "clientes" not in prompt.system
    assert "truncado" in prompt.system.lower()


def test_esquema_con_mas_columnas_se_trunca():
    prompt = construir_prompt_maestro(_esquema(), "consulta", max_schema_columns=1)
    assert prompt.esquemaTruncado is True
    assert "monto" not in prompt.system


def test_prompt_respeta_maximo_de_caracteres():
    prompt = construir_prompt_maestro(_esquema(), "consulta", max_prompt_chars=200)
    assert len(prompt.system) <= 200
    assert prompt.system.endswith(AVISO_PROMPT_TRUNCADO)


def test_prompt_truncado_corta_en_limite_de_linea():
    prompt = construir_prompt_maestro(_esquema(), "consulta", max_prompt_chars=200)
    cuerpo = prompt.system.removesuffix(AVISO_PROMPT_TRUNCADO)
    assert cuerpo.endswith("\n")


def test_prompt_incluye_guardrail_solo_tablas_del_esquema():
    prompt = construir_prompt_maestro(_esquema(), "consulta")
    assert "EXCLUSIVAMENTE tablas y columnas" in prompt.system
    assert "No derives nombres de tablas" in prompt.system
    assert "debe figurar en el esquema" in prompt.system
    assert "'Notebooks'" in prompt.system
    assert "claves foráneas del esquema" in prompt.system
    assert "recorre las claves foráneas del esquema" in prompt.system
    assert "products.mark_id" in prompt.system
    assert "marca sea Lenovo" in prompt.system
    assert "Combina SIEMPRE todos los filtros" in prompt.system
    assert "ILIKE" in prompt.system
    assert "No se puede generar una consulta SQL" in prompt.system


def test_prompt_sin_truncado_cuando_está_dentro_de_limites():
    prompt = construir_prompt_maestro(
        _esquema(), "consulta", max_schema_tables=5, max_schema_columns=10
    )
    assert prompt.esquemaTruncado is False