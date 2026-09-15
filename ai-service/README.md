# ai-service — Microservicio IA (NL → SQL)

Microservicio Python independiente que recibe una pregunta en lenguaje natural (NL) más el esquema
de la base del tenant, compone un *prompt maestro* y delega la transformación NL → SQL a una API de
IA (LLM). Devuelve únicamente la query SQL generada.

**Fuera de su alcance:** ejecutar el SQL, validar límites de plan, sanitizar contra inyección ni
persistir historial. Eso lo hace Spring Boot después de recibir el SQL.

## Stack

- Python 3.11+ · FastAPI · Pydantic v2 · async (`openai` / `anthropic`)
- Gestión de dependencias con `uv` · Tests con `pytest` · Lint con `ruff`

## Estructura

```
ai-service/
├── app/
│   ├── main.py                      # FastAPI app (POST /sql, GET /health)
│   ├── config.py                    # Settings desde variables de entorno
│   ├── api/                         # Capa de presentación (schemas + errores HTTP)
│   ├── application/                 # Capa de aplicación (caso de uso)
│   ├── domain/                      # Dominio puro (prompt, esquema, guardrails)
│   └── infrastructure/llm/          # Adaptadores del proveedor de IA (puerto + impls)
└── tests/
```

## Configuración

```bash
cp .env.example .env   # y completar OPENAI_API_KEY / ANTHROPIC_API_KEY
```

| Variable | Default | Descripción |
|---|---|---|
| `SERVICE_PORT` | `8000` | Puerto del servicio |
| `LLM_PROVIDER` | `openai` | Proveedor: `openai` \| `anthropic` |
| `LLM_MODEL` | `gpt-4o-mini-2024-07-18` | Modelo por defecto |
| `OPENAI_API_KEY` | — | Credencial OpenAI |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | — | Credencial y modelo Anthropic |
| `LLM_TIMEOUT_SECONDS` | `30` | Timeout de la llamada al LLM |
| `LLM_MAX_TOKENS` | `2048` | Máximo de tokens de la respuesta |
| `MAX_SCHEMA_TABLES` / `MAX_SCHEMA_COLUMNS` | `50` / `200` | Límites del esquema (se trunca) |
| `MAX_PROMPT_CHARS` | `8000` | Límite de caracteres del prompt final |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:8080` | Orígenes CORS permitidos |

Para usar Anthropic: `uv sync --extra anthropic`.

## Desarrollo

```bash
uv sync                 # instala dependencias
uv run uvicorn app.main:app --reload   # ejecuta en http://localhost:8000
uv run pytest           # tests
uv run ruff check .     # lint
```

## API

- `POST /sql` — transforma NL → SQL (detalle en la especificación).
- `GET /health` — estado del servicio.
- `GET /docs` · `GET /openapi.json` — OpenAPI autogenerado.

## Docker

```bash
docker build -t ai-service .
docker run -p 8000:8000 --env-file .env ai-service
```

Consumidor esperado: Spring Boot envía `POST {AI_SERVICE_BASE_URL}/sql` y re-valida el SQL recibido
antes de ejecutarlo.