import pytest
from app.application.sql_use_case import SqlUseCase
from app.config import Settings
from app.main import crear_app
from fastapi.testclient import TestClient

from tests.fakes import FakeLlmClient


@pytest.fixture
def settings() -> Settings:
    return Settings(
        llm_provider="openai",
        llm_model="modelo-de-prueba",
        openai_api_key="clave-de-prueba",
        llm_timeout_seconds=1.0,
    )


@pytest.fixture
def crear_client(settings: Settings):
    def _crear(llm: FakeLlmClient | None = None) -> TestClient:
        app = crear_app(settings)
        app.state.use_case = SqlUseCase(llm_cliente=llm or FakeLlmClient(), settings=settings)
        return TestClient(app)

    return _crear