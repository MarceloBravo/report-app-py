import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.schemas import ErrorResponse
from app.domain.errors import IaNoDevolvioSqlError, ProveedorIaIndisponibleError


def _tiempo_ms(request: Request) -> int:
    inicio = getattr(request.state, "inicio", None)
    if inicio is None:
        return 0
    return max(0, int((time.monotonic() - inicio) * 1000))


def _responder_error(request: Request, status_code: int, codigo: str, detalle: str) -> JSONResponse:
    cuerpo = ErrorResponse(error=codigo, detalle=detalle, tiempoMs=_tiempo_ms(request))
    return JSONResponse(status_code=status_code, content=cuerpo.model_dump())


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validacion(consulta: Request, error: RequestValidationError) -> JSONResponse:
        detalle = str(error.errors())
        return _responder_error(consulta, 422, "REQUEST_INVALIDO", detalle)

    @app.exception_handler(ProveedorIaIndisponibleError)
    async def _proveedor(consulta: Request, error: ProveedorIaIndisponibleError) -> JSONResponse:
        return _responder_error(consulta, 502, "PROVEEDOR_IA_INDISPONIBLE", str(error))

    @app.exception_handler(IaNoDevolvioSqlError)
    async def _sin_sql(consulta: Request, error: IaNoDevolvioSqlError) -> JSONResponse:
        return _responder_error(consulta, 503, "IA_NO_DEVOLVIO_SQL", str(error))

    @app.exception_handler(Exception)
    async def _interno(consulta: Request, error: Exception) -> JSONResponse:
        return _responder_error(consulta, 500, "ERROR_INTERNO", f"error inesperado: {error}")