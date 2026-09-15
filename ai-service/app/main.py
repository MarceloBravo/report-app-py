import time

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import registrar_manejadores
from app.api.schemas import RequestSql, ResponseSql
from app.application.sql_use_case import SqlUseCase
from app.config import Settings, get_settings
from app.infrastructure.llm.factory import crear_cliente


def _obtener_use_case(consulta: Request) -> SqlUseCase:
    return consulta.app.state.use_case


def crear_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title="Microservicio IA (NL → SQL)",
        description=(
            "Transforma una pregunta en lenguaje natural en una consulta SQL PostgreSQL 16."
        ),
        version="0.1.0",
    )

    app.state.settings = settings
    app.state.use_case = SqlUseCase(llm_cliente=crear_cliente(settings), settings=settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _medir_tiempo(consulta: Request, call_next):
        consulta.state.inicio = time.monotonic()
        return await call_next(consulta)

    registrar_manejadores(app)

    @app.get("/health")
    async def salud() -> dict[str, str]:
        return {"estado": "ok"}

    @app.post("/sql", response_model=ResponseSql)
    async def generar_sql(consulta: RequestSql, caso: SqlUseCase = Depends(_obtener_use_case)):
        return await caso.generar(consulta)

    return app


app = crear_app()