from pydantic import BaseModel, Field

from app.domain.esquema import EsquemaTenant


class RequestSql(BaseModel):
    tenantId: str
    usuarioId: str
    preguntaUsuario: str = Field(min_length=1)
    esquema: EsquemaTenant


class ResponseSql(BaseModel):
    tenantId: str
    querySql: str
    exitosa: bool = True
    tiempoMs: int


class ErrorResponse(BaseModel):
    error: str
    detalle: str
    tiempoMs: int