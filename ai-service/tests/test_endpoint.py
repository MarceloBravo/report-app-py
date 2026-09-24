from app.domain.errors import ProveedorIaIndisponibleError

from tests.fakes import FakeLlmClient

CUERPO_VALIDO = {
    "tenantId": "t-1",
    "usuarioId": "u-1",
    "preguntaUsuario": "¿Cuántas ventas hubo por mes en 2025?",
    "esquema": {
        "tablas": [
            {
                "nombre": "ventas",
                "columnas": [
                    {"nombre": "id", "tipoDato": "uuid", "nullable": False, "esPrimaryKey": True},
                    {"nombre": "monto", "tipoDato": "numeric", "nullable": False},
                    {"nombre": "fecha", "tipoDato": "timestamp", "nullable": False},
                ],
            }
        ]
    },
}


def test_sql_200_con_proveedor_fake(crear_client):
    llm = FakeLlmClient(sql="SELECT monto FROM ventas WHERE fecha >= '2025-01-01'")
    cliente = crear_client(llm)
    respuesta = cliente.post("/sql", json=CUERPO_VALIDO)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["tenantId"] == "t-1"
    assert cuerpo["exitosa"] is True
    assert cuerpo["querySql"].startswith("SELECT")
    assert isinstance(cuerpo["tiempoMs"], int)


def test_sql_503_respuesta_vacia(crear_client):
    cliente = crear_client(FakeLlmClient(sql=""))
    respuesta = cliente.post("/sql", json=CUERPO_VALIDO)
    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["error"] == "IA_NO_DEVOLVIO_SQL"
    assert isinstance(cuerpo["tiempoMs"], int)


def test_sql_503_respuesta_no_select(crear_client):
    cliente = crear_client(FakeLlmClient(sql="DELETE FROM ventas"))
    respuesta = cliente.post("/sql", json=CUERPO_VALIDO)
    assert respuesta.status_code == 503
    assert respuesta.json()["error"] == "IA_NO_DEVOLVIO_SQL"


def test_sql_502_proveedor_caido(crear_client):
    llm = FakeLlmClient()
    llm.excepcion = ProveedorIaIndisponibleError("timeout del proveedor")
    cliente = crear_client(llm)
    respuesta = cliente.post("/sql", json=CUERPO_VALIDO)
    assert respuesta.status_code == 502
    cuerpo = respuesta.json()
    assert cuerpo["error"] == "PROVEEDOR_IA_INDISPONIBLE"
    assert isinstance(cuerpo["tiempoMs"], int)


def test_sql_422_campos_faltantes(crear_client):
    cliente = crear_client()
    cuerpo = dict(CUERPO_VALIDO)
    cuerpo.pop("preguntaUsuario")
    respuesta = cliente.post("/sql", json=cuerpo)
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "REQUEST_INVALIDO"


def test_health_ok(crear_client):
    cliente = crear_client()
    respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


def test_openapi_disponible(crear_client):
    cliente = crear_client()
    assert cliente.get("/docs").status_code == 200
    assert cliente.get("/openapi.json").status_code == 200


def test_sql_200_con_proveedor_fake_dos_pasadas_por_relaciones(crear_client):
    cuerpo = {
        "tenantId": "t-cat",
        "usuarioId": "u-1",
        "preguntaUsuario": "Notebooks cuya marca sea Lenovo",
        "esquema": {
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
                {"nombre": "marks", "columnas": [{"nombre": "id", "tipoDato": "uuid"}]},
            ]
        },
    }
    borrador = "SELECT p.* FROM products p WHERE p.name LIKE 'Lenovo%'"
    corregido = (
        "SELECT p.* FROM products p JOIN marks m ON p.mark_id = m.id "
        "WHERE m.name LIKE 'Lenovo%'"
    )
    llm = FakeLlmClient(respuestas=[borrador, corregido])
    cliente = crear_client(llm)
    respuesta = cliente.post("/sql", json=cuerpo)
    assert respuesta.status_code == 200
    assert "JOIN marks m" in respuesta.json()["querySql"]
    assert len(llm.llamadas) == 2


def test_sql_con_revision_invalida_conserva_original(crear_client):
    cuerpo = {
        "tenantId": "t-cat",
        "usuarioId": "u-1",
        "preguntaUsuario": "Notebooks cuya marca sea Lenovo",
        "esquema": {
            "tablas": [
                {
                    "nombre": "products",
                    "columnas": [
                        {"nombre": "id", "tipoDato": "uuid", "esPrimaryKey": True},
                        {
                            "nombre": "mark_id",
                            "tipoDato": "uuid",
                            "esForeignKey": True,
                            "tablaReferenciada": "marks",
                            "columnaReferenciada": "id",
                        },
                    ],
                },
                {"nombre": "marks", "columnas": [{"nombre": "id", "tipoDato": "uuid"}]},
            ]
        },
    }
    borrador = "SELECT p.* FROM products p"
    llm = FakeLlmClient(respuestas=[borrador, ""])
    cliente = crear_client(llm)
    respuesta = cliente.post("/sql", json=cuerpo)
    assert respuesta.status_code == 200
    assert respuesta.json()["querySql"] == borrador
    assert len(llm.llamadas) == 2