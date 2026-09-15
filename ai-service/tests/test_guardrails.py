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
        "SELECT 1;",
        "SELECT 1 -- comentario",
        "SELECT 1 /* comentario */",
    ],
)
def test_con_comentarios_o_punto_y_coma_falla(sql):
    with pytest.raises(IaNoDevolvioSqlError):
        validar_sql_generado(sql)