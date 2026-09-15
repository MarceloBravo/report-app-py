from app.infrastructure.llm.base import LlmClient
from app.infrastructure.llm.factory import crear_cliente
from app.infrastructure.llm.openai_client import OpenAILLMClient

from tests.fakes import FakeLlmClient


def test_fake_implementa_la_interfaz():
    assert isinstance(FakeLlmClient(sql="SELECT 1"), LlmClient)


def test_fake_devuelve_sql_configurado():
    cliente = FakeLlmClient(sql="SELECT 1")
    assert cliente.respuesta == "SELECT 1"


def test_factory_crea_openai_por_defecto(settings):
    cliente = crear_cliente(settings)
    assert isinstance(cliente, OpenAILLMClient)


def test_factory_rechaza_proveedor_desconocido(settings):
    settings.llm_provider = "gemini"
    try:
        crear_cliente(settings)
    except ValueError as error:
        assert "no soportado" in str(error)
    else:
        raise AssertionError("debería lanzar ValueError")