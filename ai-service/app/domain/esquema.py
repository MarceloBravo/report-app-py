from pydantic import BaseModel, Field


class ColumnaEsquema(BaseModel):
    nombre: str
    tipoDato: str
    nullable: bool = True
    esPrimaryKey: bool = False


class TablaEsquema(BaseModel):
    nombre: str
    columnas: list[ColumnaEsquema] = Field(default_factory=list)


class EsquemaTenant(BaseModel):
    tablas: list[TablaEsquema] = Field(default_factory=list)