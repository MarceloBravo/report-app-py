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


def test_factory_ollama_apunta_a_localhost(settings):
    settings.llm_provider = "ollama"
    settings.llm_model = "qwen2.5-coder:7b"
    cliente = crear_cliente(settings)
    assert isinstance(cliente, OpenAILLMClient)
    assert "11434" in str(cliente._client.base_url)


def test_factory_ollama_respeta_base_url_personalizada(settings):
    settings.llm_provider = "ollama"
    settings.llm_base_url = "http://host.docker.internal:11434/v1"
    cliente = crear_cliente(settings)
    assert "host.docker.internal" in str(cliente._client.base_url)


def test_factory_openai_respeta_base_url_personalizada(settings):
    settings.llm_base_url = "https://otro-proveedor.example/v1"
    cliente = crear_cliente(settings)
    assert "otro-proveedor.example" in str(cliente._client.base_url)


def test_factory_rechaza_proveedor_desconocido(settings):
    settings.llm_provider = "gemini"
    try:
        crear_cliente(settings)
    except ValueError as error:
        assert "no soportado" in str(error)
    else:
        raise AssertionError("debería lanzar ValueError")