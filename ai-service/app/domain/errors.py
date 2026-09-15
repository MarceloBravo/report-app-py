class IaServiceError(Exception):
    """Error base del microservicio."""


class ProveedorIaIndisponibleError(IaServiceError):
    """El proveedor de IA falló, devolvió error o superó el timeout."""


class IaNoDevolvioSqlError(IaServiceError):
    """El LLM devolvió una respuesta vacía o que no supera los guardrails."""