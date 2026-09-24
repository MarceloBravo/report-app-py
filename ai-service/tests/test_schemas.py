import pytest
from app.api.schemas import ErrorResponse, RequestSql, ResponseSql
from pydantic import ValidationError

ESQUEMA_BASICO = {
    "tablas": [
        {
            "nombre": "ventas",
            "columnas": [
                {
                    "tabla": "ventas",
                    "nombre": "id",
                    "tipoDato": "uuid",
                    "nullable": False,
                    "esPrimaryKey": True,
                },
                {
                    "tabla": "ventas",
                    "nombre": "monto",
                    "tipoDato": "numeric",
                    "nullable": False,
                    "esPrimaryKey": False,
                },
                {
                    "tabla": "ventas",
                    "nombre": "fecha",
                    "tipoDato": "timestamp",
                    "nullable": False,
                    "esPrimaryKey": False,
                },
            ],
        }
    ]
}

CUERPO_VALIDO = {
    "tenantId": "t-1",
    "usuarioId": "u-1",
    "preguntaUsuario": "¿Cuántas ventas hubo por mes en 2025?",
    "esquema": ESQUEMA_BASICO,
}


def test_request_sql_valido():
    request = RequestSql.model_validate(CUERPO_VALIDO)
    assert request.tenantId == "t-1"
    assert request.esquema.tablas[0].nombre == "ventas"
    assert request.esquema.tablas[0].columnas[0].esPrimaryKey is True
    assert request.esquema.tablas[0].columnas[0].tabla == "ventas"


def test_request_reconoce_relaciones_entre_tablas():
    cuerpo = dict(CUERPO_VALIDO)
    cuerpo["esquema"] = {
        "tablas": [
            {
                "nombre": "ventas",
                "columnas": [
                    {
                        "tabla": "ventas",
                        "nombre": "cliente_id",
                        "tipoDato": "uuid",
                        "nullable": False,
                        "esPrimaryKey": False,
                        "esForeignKey": True,
                        "tablaReferenciada": "clientes",
                        "columnaReferenciada": "id",
                    }
                ],
            },
            {"nombre": "clientes", "columnas": [{"nombre": "id", "tipoDato": "uuid"}]},
        ]
    }
    request = RequestSql.model_validate(cuerpo)
    columna = request.esquema.tablas[0].columnas[0]
    assert columna.tabla == "ventas"
    assert columna.esForeignKey is True
    assert columna.tablaReferenciada == "clientes"
    assert columna.columnaReferenciada == "id"


def test_request_relaciones_omiten_campos_usando_defaults():
    cuerpo = dict(CUERPO_VALIDO)
    columna = RequestSql.model_validate(cuerpo).esquema.tablas[0].columnas[0]
    assert columna.esForeignKey is False
    assert columna.tablaReferenciada is None
    assert columna.columnaReferenciada is None


def test_request_acepta_nulos_en_campos_de_relacion():
    cuerpo = dict(CUERPO_VALIDO)
    cuerpo["esquema"] = {
        "tablas": [
            {
                "nombre": "ventas",
                "columnas": [
                    {
                        "tabla": "ventas",
                        "nombre": "cliente_id",
                        "tipoDato": "uuid",
                        "nullable": False,
                        "esPrimaryKey": False,
                        "esForeignKey": True,
                        "tablaReferenciada": "clientes",
                        "columnaReferenciada": "id",
                    },
                    {
                        "tabla": None,
                        "nombre": "monto",
                        "tipoDato": "numeric",
                        "nullable": True,
                        "esPrimaryKey": False,
                        "esForeignKey": False,
                        "tablaReferenciada": None,
                        "columnaReferenciada": None,
                    },
                ],
            }
        ]
    }
    request = RequestSql.model_validate(cuerpo)
    monto = request.esquema.tablas[0].columnas[1]
    assert monto.tabla is None
    assert monto.esForeignKey is False
    assert monto.tablaReferenciada is None


@pytest.mark.parametrize(
    "campo_omitido",
    ["tenantId", "usuarioId", "preguntaUsuario", "esquema"],
)
def test_request_omite_campo_requerido_falla(campo_omitido):
    cuerpo = dict(CUERPO_VALIDO)
    cuerpo.pop(campo_omitido)
    with pytest.raises(ValidationError):
        RequestSql.model_validate(cuerpo)


def test_request_pregunta_vacia_falla():
    cuerpo = dict(CUERPO_VALIDO)
    cuerpo["preguntaUsuario"] = ""
    with pytest.raises(ValidationError):
        RequestSql.model_validate(cuerpo)


def test_response_sql_serializa():
    response = ResponseSql(tenantId="t-1", querySql="SELECT 1", exitosa=True, tiempoMs=12)
    datos = response.model_dump()
    assert datos == {
        "tenantId": "t-1",
        "querySql": "SELECT 1",
        "exitosa": True,
        "tiempoMs": 12,
    }


def test_error_response_serializa():
    error = ErrorResponse(error="ERROR_INTERNO", detalle="boom", tiempoMs=3)
    assert error.model_dump() == {"error": "ERROR_INTERNO", "detalle": "boom", "tiempoMs": 3}