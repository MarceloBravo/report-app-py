from pydantic import BaseModel, Field


class ColumnaEsquema(BaseModel):
    tabla: str | None = None
    nombre: str
    tipoDato: str
    nullable: bool = True
    esPrimaryKey: bool = False
    esForeignKey: bool = False
    tablaReferenciada: str | None = None
    columnaReferenciada: str | None = None


class TablaEsquema(BaseModel):
    nombre: str
    columnas: list[ColumnaEsquema] = Field(default_factory=list)


class EsquemaTenant(BaseModel):
    tablas: list[TablaEsquema] = Field(default_factory=list)

    @property
    def tiene_relaciones(self) -> bool:
        return any(
            columna.esForeignKey and columna.tablaReferenciada
            for tabla in self.tablas
            for columna in tabla.columnas
        )