from app.domain.esquema import EsquemaTenant
from app.domain.prompt import construir_prompt_maestro


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


def test_prompt_sin_truncado_cuando_está_dentro_de_limites():
    prompt = construir_prompt_maestro(
        _esquema(), "consulta", max_schema_tables=5, max_schema_columns=10
    )
    assert prompt.esquemaTruncado is False