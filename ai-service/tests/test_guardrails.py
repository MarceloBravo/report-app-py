import pytest
from app.domain.errors import IaNoDevolvioSqlError
from app.domain.guardrails import validar_sql_generado


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