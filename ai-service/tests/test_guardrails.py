import pytest
from app.domain.errors import IaNoDevolvioSqlError
from app.domain.esquema import EsquemaTenant
from app.domain.guardrails import validar_sql_generado


def _esquema_ventas() -> EsquemaTenant:
    return EsquemaTenant.model_validate(
        {
            "tablas": [
                {
                    "nombre": "ventas",
                    "columnas": [
                        {"nombre": "id", "tipoDato": "uuid", "esPrimaryKey": True},
                        {"nombre": "monto", "tipoDato": "numeric", "nullable": False},
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


def test_acepta_select_normalizada():
    assert validar_sql_generado("  SELECT 1  ") == "SELECT 1"


@pytest.mark.parametrize("sql", ["", "   ", None])
def test_respuesta_vacia_falla(sql):
    with pytest.raises(IaNoDevolvioSqlError):
        validar_sql_generado(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO ventas VALUES (1)",
        "UPDATE ventas SET monto = 1",
        "DELETE FROM ventas",
        "DROP TABLE ventas",
    ],
)
def test_no_es_select_falla(sql):
    with pytest.raises(IaNoDevolvioSqlError):
        validar_sql_generado(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; SELECT 2",
        "SELECT 1 -- comentario",
        "SELECT 1 /* comentario */",
    ],
)
def test_con_comentarios_o_punto_y_coma_interior_falla(sql):
    with pytest.raises(IaNoDevolvioSqlError):
        validar_sql_generado(sql)


@pytest.mark.parametrize(
    "sql,esperado",
    [
        ("SELECT 1;", "SELECT 1"),
        ("SELECT 1;;;", "SELECT 1"),
        ("SELECT 1 ; ", "SELECT 1"),
    ],
)
def test_punto_y_coma_final_se_elimina(sql, esperado):
    assert validar_sql_generado(sql) == esperado


@pytest.mark.parametrize(
    "sql,esperado",
    [
        ("```sql\nSELECT 1\n```", "SELECT 1"),
        ("```\nSELECT 1;\n```", "SELECT 1"),
        ("```sql\r\nSELECT SUM(monto) FROM ventas\r\n```", "SELECT SUM(monto) FROM ventas"),
    ],
)
def test_quita_cerco_markdown_sql(sql, esperado):
    assert validar_sql_generado(sql) == esperado


def test_cerco_markdown_con_punto_y_coma_interior_falla():
    with pytest.raises(IaNoDevolvioSqlError):
        validar_sql_generado("```sql\nDELETE FROM ventas;\n```")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1\nFROM ventas",
        "SELECT 1\\nFROM ventas\n",
        "SELECT 1\r\nFROM ventas\r\n",
        "SELECT SUM(monto) \\n FROM ventas \\n",
        "SELECT 1\\tFROM ventas",
    ],
)
def test_sql_se_normaliza_a_una_sola_linea(sql):
    resultado = validar_sql_generado(sql)
    assert "\n" not in resultado
    assert "\\n" not in resultado
    assert "\\t" not in resultado


def test_sql_con_tabla_ausente_falla():
    with pytest.raises(IaNoDevolvioSqlError, match="vendedores"):
        validar_sql_generado("SELECT v.id FROM vendedores v", _esquema_ventas())


def test_sql_con_tabla_inexistente_en_join_falla():
    with pytest.raises(IaNoDevolvioSqlError, match="clientes_extranjeros"):
        validar_sql_generado(
            "SELECT * FROM ventas v INNER JOIN clientes_extranjeros c ON c.id = v.id",
            _esquema_ventas(),
        )


def test_sql_con_tablas_del_esquema_pasa():
    sql = "SELECT SUM(v.monto) FROM ventas v JOIN clientes c ON c.id = v.id"
    assert validar_sql_generado(sql, _esquema_ventas()) == sql


def test_sql_sin_esquema_no_valida_tablas():
    sql = "SELECT 1 FROM tabla_cualquiera"
    assert validar_sql_generado(sql) == sql


def test_sql_con_cte_pasa():
    sql = (
        "WITH ingresos AS (SELECT fecha, SUM(monto) AS total FROM ventas GROUP BY fecha) "
        "SELECT fecha FROM ingresos WHERE total > 100"
    )
    assert validar_sql_generado(sql, _esquema_ventas()) == sql


def test_literal_que_contiene_from_no_es_tabla():
    sql = "SELECT nombre FROM clientes WHERE pais = 'FROM clientes'"
    assert validar_sql_generado(sql, _esquema_ventas()) == sql


def test_cte_que_usa_tabla_inexistente_falla():
    with pytest.raises(IaNoDevolvioSqlError, match="tabla_fantasma"):
        validar_sql_generado(
            "WITH x AS (SELECT * FROM tabla_fantasma) SELECT * FROM x",
            _esquema_ventas(),
        )