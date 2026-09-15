# Especificación — Microservicio IA (NL → SQL)

**Documento de referencia para la creación del proyecto independiente.**
Fecha: 2026-09-14 · Estado: Especificación de creación

---

## 1. Objetivo

Microservicio Python independiente que recibe una pregunta en lenguaje natural (NL) más el esquema
de la base del tenant, compone un *prompt maestro* y delega la transformación NL → SQL a una API de
IA (LLM). Devuelve únicamente la query SQL generada.

**No es responsabilidad de este servicio:** ejecutar el SQL, validar límites de plan, sanitizar contra
inyección ni persistir historial. Eso lo hace Spring Boot después de recibir el SQL.

---

## 2. Decisión de ubicación

Proyecto **independiente y desplegable por separado** (repositorio git propio, fuera del árbol Maven
de Spring Boot).

Estructura de monorepo aceptable (mínima):

```
report/                  (Spring Boot — proyecto existente, con su pom.xml)
report/ai-service/       (Python FastAPI — este proyecto, recién creado)
```

Regla: **nunca** dentro de `report/src/` ni de `report/bin/`.

---

## 3. Stack tecnológico

| Capa | Elección | Justificación |
|------|----------|---------------|
| Lenguaje | Python 3.11+ | Ecosistema LLM nativo |
| Framework web | **FastAPI** | Async, validación Pydantic, OpenAPI autogenerado, estándar en microservicios de IA |
| Validación | Pydantic v2 | Contrato tipado de request/response |
| Cliente HTTP LLM | Por proveedor (ver §7) | Abstraible tras una interfaz común |
| Ejecución HTTP | Async (`httpx` o cliente oficial del proveedor) | No bloquear mientras espera al LLM |
| Dependencias | `pyproject.toml` + `uv` (o `poetry`) | Preferir `uv` por velocidad y simplicidad |
| Docker | `python:3.12-slim` + `uv` / `pip` | Imagen mínima |
| Calidad | `pytest` + `ruff` | Tests unitarios y lint |

---

## 4. Estructura de directorios

```
ai-service/
├── pyproject.toml
├── README.md
├── .env.example
├── .gitignore
├── Dockerfile
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app + endpoint
│   ├── config.py               # Settings pydantic-settings (env vars)
│   ├── schemas.py              # Modelos Pydantic de request/response/errores
│   ├── prompt.py               # Composición del prompt maestro (sin secretos)
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py             # Interfaz abstracta LlmClient
│   │   ├── openai_client.py    # Implementación OpenAI (default)
│   │   ├── anthropic_client.py # Implementación Anthropic (opcional)
│   │   └── factory.py          # Selección de cliente según env AOAI_PROVIDER
│   └── errors.py               # Excepciones de dominio del servicio
└── tests/
    ├── test_schemas.py
    ├── test_prompt.py
    ├── test_endpoint.py
    └── test_llm_base.py        # Con cliente fake/stub (sin coste de API)
```

---

## 5. Contrato HTTP

### 5.1 `POST /sql`

Transforma una pregunta en lenguaje natural a SQL usando el esquema recibido.

**Request**

```json
{
  "tenantId": "uuid",
  "usuarioId": "uuid",
  "preguntaUsuario": "¿Cuántas ventas hubo por mes en 2025?",
  "esquema": {
    "tablas": [
      {
        "nombre": "ventas",
        "columnas": [
          { "nombre": "id", "tipoDato": "uuid", "nullable": false, "esPrimaryKey": true },
          { "nombre": "monto", "tipoDato": "numeric", "nullable": false, "esPrimaryKey": false },
          { "nombre": "fecha", "tipoDato": "timestamp", "nullable": false, "esPrimaryKey": false }
        ]
      }
    ]
  }
}
```

> El `esquema` reproduce el modelo del módulo `tenant` de Spring Boot:
> `EsquemaTenant(tenantId, List<TablaEsquema>, extraidoEn)`,
> `TablaEsquema(nombre, List<ColumnaEsquema>)`,
> `ColumnaEsquema(nombre, tipoDato, nullable, esPrimaryKey)`.
> El campo `extraidoEn` no es necesario enviarlo al LLM; solo `tablas` es obligatorio.

**Respuesta 200**

```json
{
  "tenantId": "uuid",
  "querySql": "SELECT ... FROM ventas WHERE ...",
  "exitosa": true,
  "tiempoMs": 1234
}
```

### 5.2 Respuestas de error

Todas usan el formato:

```json
{
  "error": "CODIGO",
  "detalle": "Mensaje legible",
  "tiempoMs": 50
}
```

| HTTP | Código | Caso |
|------|--------|------|
| 400 | `REQUEST_INVALIDO` | JSON malformado o validación Pydantic fallida |
| 422 | (Pydantic) | Campos requeridos faltantes o tipo incorrecto |
| 502 | `PROVEEDOR_IA_INDISPONIBLE` | Timeout o error del proveedor LLM |
| 503 | `IA_NO_DEVOLVIO_SQL` | El LLM devolvió respuesta vacía o sin SQL parseable |
| 500 | `ERROR_INTERNO` | Cualquier excepción no esperada |

---

## 6. Composición del prompt maestro

El prompt se ensambla en `prompt.py` (función pura, sin secretos ni llamadas I/O). Debe:

1. Definir el rol del sistema (generador de SQL de solo lectura).
2. Incluir el **esquema completo** (tablas y columnas con tipo).
3. Enumerar las **reglas del guardrails**:
   - Solo generar sentencia `SELECT` (prohibido INSERT/UPDATE/DELETE/DDL).
   - No usar `;` final ni comentarios `--`/`/* */`.
   - Usar SQL estándar PostgreSQL 16.
   - Responder **únicamente** con el SQL, sin explicaciones, sin markdown.
4. Incluir la pregunta del usuario.

Los guardrails son la primera línea de defensa; Spring Boot re-valida sintácticamente igual después
(línea de defensa autoritativa).

---

## 7. Abstracción del proveedor de IA

Interfaz única en `llm/base.py`:

```python
class LlmClient(ABC):
    @abstractmethod
    async def generar_sql(self, system_prompt: str, pregunta: str) -> str: ...
```

- Default: **OpenAI** (`openai_client.py`) — modelo configurable vía env (`AOAI_MODEL`).
- Opcional: Anthropic (`anthropic_client.py`) con la misma interfaz.
- `factory.py` elige implementación según `AOAI_PROVIDER`.
- Tests usan un `FakeLlmClient` (retorna SQL fijo) para no consumir tokens.

Llamada al LLM: `temperature=0` (máxima determinismo en SQL), timeout configurable.

---

## 8. Configuración por variables de entorno

`.env.example` (copiar a `.env` local; este archivo es de creación, no de ejecución):

```bash
# Puerto del servicio
SERVICE_PORT=8000

# Proveedor LLM (openai | anthropic)
AOAI_PROVIDER=openai

# Credenciales del proveedor (nunca se hardcodea)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini-2024-07-18

# ANTHROPIC_API_KEY=...
# ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Límites y timeouts
LLM_TIMEOUT_SECONDS=30
MAX_SCHEMA_TABLES=50
MAX_SCHEMA_COLUMNS=200
MAX_PROMPT_CHARS=8000

# CORS (para desarrollo con Spring Boot local)
CORS_ALLOWED_ORIGINS=http://localhost:8080
```

- El esquema se trunca si excede `MAX_SCHEMA_TABLES`/`MAX_SCHEMA_COLUMNS` (protección contra prompts
  gigantes). Se envía una advertencia al LLM en el prompt si se truncó.
- `MAX_PROMPT_CHARS` limita el prompt final enviado.

---

## 9. Dockerfile

```dockerfile
FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --no-dev

COPY app ./app

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 10. Pruebas

- `tests/test_schemas.py` — validación Pydantic de request/response y errores 422.
- `tests/test_prompt.py` — composición del prompt: contiene esquema, no contiene secretos, aplica truncado.
- `tests/test_endpoint.py` — FastAPI TestClient con `FakeLlmClient`: 200 con SQL, 502 con fallo del proveedor, 503 con respuesta vacía.
- `tests/test_llm_base.py` — contrato de la interfaz con el cliente fake.

Ejecutar: `uv run pytest` · Lint: `uv run ruff check .`

---

## 11. Criterios de aceptación

- [ ] `POST /sql` devuelve 200 con `querySql` válido (empieza con `SELECT`, sin `;` ni comentarios) para un esquema simple.
- [ ] Con respuesta LLM vacía → `503` (`IA_NO_DEVOLVIO_SQL`).
- [ ] Con proveedor caído/timeout → `502` (`PROVEEDOR_IA_INDISPONIBLE`).
- [ ] El esquema con > `MAX_SCHEMA_TABLES` se trunca sin error.
- [ ] Ningún secreto (API key) aparece en el prompt ni en los logs.
- [ ] OpenAPI disponible en `GET /docs` y `GET /openapi.json`.
- [ ] Dockerfile construye e inicia el servicio en el puerto configurado.
- [ ] Suite de tests pasa con proveedor fake (sin coste de API).

---

## 12. Integración futura con Spring Boot (contrato esperado)

- Spring Boot consumirá `POST {AI_SERVICE_BASE_URL}/sql` con el cuerpo de §5.1.
- Spring Boot nunca expone el servicio Python al frontend; solo `POST /consultas`.
- Base URL conforme a entorno: `AI_SERVICE_BASE_URL=http://localhost:8000` (dev).
- Spring Boot re-valida el SQL recibido (solo `SELECT`, sin `;`, sin `--`) antes de ejecutarlo
  (línea de defensa autoritativa según `docs/Diagrama_Secuencia_Consulta.md` §8).