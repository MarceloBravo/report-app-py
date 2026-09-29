# ai-service — Microservicio IA (NL → SQL)

Microservicio Python independiente que recibe una pregunta en lenguaje natural (NL) más el esquema
de la base del tenant, compone un *prompt maestro* y delega la transformación NL → SQL a una API de
IA (LLM). Devuelve únicamente la query SQL generada.

**Fuera de su alcance:** ejecutar el SQL, validar límites de plan, sanitizar contra inyección ni
persistir historial. Eso lo hace Spring Boot después de recibir el SQL.

Especificación funcional completa: [`../Microservicio-IA-Especificacion.md`](../Microservicio-IA-Especificacion.md).

---

## 1. Arquitectura

### 1.1 Contexto de despliegue

```
┌──────────────┐   POST /consultas    ┌────────────────────┐   POST /sql    ┌──────────────────┐
│   Frontend   │ ───────────────────► │  Spring Boot       │ ─────────────► │   ai-service     │
│  (navegador) │ ◄─────────────────── │  report-app-py     │ ◄───────────── │   (FastAPI)      │
└──────────────┘   JSON + resultados  │  valida y ejecuta  │  querySql      └────────┬─────────┘
                                    └────────────────────┘                             │
                                                                    LlmClient (puerto)│
                                                                     ┌─────────────────┴──────────────────┐
                                                                     │  API de IA                       │
                                                                     │  • Comercial: OpenAI/Anthropic   │
                                                                     │  • Local/remoto: Ollama +        │
                                                                     │    qwen2.5-coder:7b              │
                                                                     └────────────────────────────────────┘
```

Puntos clave del diseño:

- **Spring Boot es la única puerta de entrada.** Nunca expone este servicio al frontend.
- **ai-service es agnóstico al proveedor de IA**: habla con cualquier endpoint compatible con la
  API de OpenAI (OpenAI, Azure OpenAI, Ollama, LM Studio, vLLM, llama.cpp server…).
- **Sin estado**: el servicio no persiste nada, no cachea, no guarda historial. Cada `POST /sql` es
  una invocación independiente al LLM.
- **Guardrails en dos capas**: el prompt impone las reglas al LLM y el servicio valida la respuesta
  (`app/domain/guardrails.py`); Spring Boot re-valida el SQL de forma autoritativa antes de ejecutar.

### 1.2 Arquitectura interna (Clean Architecture / Ports & Adapters)

```
app/
├── main.py                        # Composición: crea FastAPI, CORS, middleware, state
├── config.py                      # Settings (pydantic-settings) ← variables de entorno
│
├── api/                           # ▸ CAPA DE PRESENTACIÓN
│   ├── schemas.py                 #   Modelos Pydantic de request/response/error
│   └── errors.py                  #   Manejadores de excepción → respuestas HTTP
│
├── application/                   # ▸ CAPA DE APLICACIÓN (caso de uso)
│   └── sql_use_case.py            #   Orquesta: prompt → LLM → guardrails → (revisión) → respuesta
│
├── domain/                        # ▸ DOMINIO PURO (sin I/O, sin dependencias externas)
│   ├── prompt.py                  #   Prompt maestro + prompt de revisión; plantilla del esquema
│   ├── esquema.py                 #   Modelo del esquema del tenant (tablas, columnas, FKs)
│   ├── guardrails.py              #   Validación del SQL devuelto por el LLM
│   └── errors.py                  #   Excepciones de dominio
│
└── infrastructure/llm/            # ▸ ADAPTADORES (puerto + implementaciones)
    ├── base.py                    #   Puerto abstracto  LlmClient.generar_sql()
    ├── openai_client.py           #   Impl. compatible con la API de OpenAI (sirve para Ollama)
    ├── anthropic_client.py        #   Impl. Anthropic (opcional, extra `anthropic`)
    └── factory.py                 #   Selección de implementación según LLM_PROVIDER
```

**Flujo de una petición `POST /sql`:**

1. `api/schemas.py` valida el cuerpo (`RequestSql`): Pydantic devuelve 422 si algo no cumple.
2. `application/sql_use_case.py` llama a `domain/prompt.py` para componer el *prompt maestro*
   (rol + guardrails + esquema truncado + relaciones FK + pregunta).
3. `infrastructure/llm/factory.py` ya resolvió el `LlmClient` en el arranque; se invoca
   `generar_sql(system_prompt, pregunta)` con `temperature=0`.
4. `domain/guardrails.py` normaliza (una sola línea, sin markdown, sin `;` final) y valida:
   - debe ser un único `SELECT`/`WITH … SELECT`;
   - sin `;`, sin comentarios `--` ni `/* */`;
   - toda tabla de `FROM`/`JOIN` debe existir en el esquema (los CTE se admiten).
5. Si el esquema **tiene claves foráneas** y `LLM_REVISAR_FK=true`, se hace una **segunda pasada**
   al LLM para corregir JOINs y columnas de filtro. Si esa revisión no supera los guardrails se
   conserva el SQL original (nunca se degrada la respuesta).
6. Se responde `{ tenantId, querySql, exitosa, tiempoMs }` o un error tipificado.

### 1.3 Contrato HTTP

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/sql` | Transforma NL → SQL. Detalle en la especificación (§5.1). |
| `GET` | `/health` | Estado del servicio: `{"estado": "ok"}`. |
| `GET` | `/docs` · `/openapi.json` | OpenAPI autogenerado por FastAPI. |

**Request**

```json
{
  "tenantId": "tenant-01",
  "usuarioId": "user-01",
  "preguntaUsuario": "Notebooks cuya marca sea Lenovo",
  "esquema": {
    "tablas": [
      {
        "nombre": "products",
        "columnas": [
          { "nombre": "id", "tipoDato": "int4", "esPrimaryKey": true },
          { "nombre": "mark_id", "tipoDato": "int4", "esForeignKey": true,
            "tablaReferenciada": "marks", "columnaReferenciada": "id" }
        ]
      },
      { "nombre": "marks", "columnas": [ { "nombre": "name", "tipoDato": "varchar" } ] }
    ]
  }
}
```

**Respuesta 200**

```json
{ "tenantId": "tenant-01", "querySql": "SELECT p.* FROM products p JOIN marks m ON p.mark_id = m.id WHERE m.name = 'Lenovo'", "exitosa": true, "tiempoMs": 2140 }
```

**Errores** (`{ error, detalle, tiempoMs }`)

| HTTP | `error` | Causa |
|---|---|---|
| 422 | `REQUEST_INVALIDO` | Body que no cumple el contrato Pydantic. |
| 502 | `PROVEEDOR_IA_INDISPONIBLE` | LLM caído, timeout, credencial inválida, red. |
| 503 | `IA_NO_DEVOLVIO_SQL` | El LLM devolvió vacío, no un `SELECT`, o tabla inexistente. |
| 500 | `ERROR_INTERNO` | Cualquier otro fallo. |

---

## 2. Tecnologías utilizadas

| Capa | Tecnología | Versión / detalle |
|---|---|---|
| Lenguaje | Python | `>=3.11` (imagen Docker `python:3.12-slim`) |
| Framework web | FastAPI | `>=0.115,<1` — async, OpenAPI autogenerado |
| Servidor ASGI | Uvicorn | `uvicorn[standard]>=0.30,<1` |
| Validación / contratos | Pydantic v2 | `>=2.7,<3` |
| Configuración | pydantic-settings | `>=2.3,<3` (lee `.env` + variables de entorno) |
| Cliente LLM (OpenAI-compatible) | `openai` (AsyncOpenAI) | `>=1.40,<2` — también sirve para Ollama |
| Cliente LLM (Anthropic) | `anthropic` | `>=0.34,<1` — extra opcional |
| Gestión de dependencias | `uv` | `pyproject.toml` + `uv.lock` |
| Tests | pytest · pytest-asyncio · httpx | `asyncio_mode = "auto"` |
| Lint / formato | ruff | `line-length = 100`, reglas `E,F,I,UP,B,SIM` |
| Debug | debugpy | Configuración en `.vscode/launch.json` |
| Contenedor | Docker | Imagen mínima con `uv`, expone el puerto 8000 |
| Motor de IA | **Ollama + `qwen2.5-coder:7b`** | Local o en otra máquina de la red (ver §5) |

---

## 3. Prerrequisitos

### 3.1 Comunes

- **Python 3.11 o superior** (o Docker Desktop).
- **[uv](https://docs.astral.sh/uv/)** para instalar dependencias: `pip install uv` o
  `winget install --id=astral-sh.uv`.
- Acceso de red al **proveedor de IA** elegido.
- La aplicación **Spring Boot** https://github.com/MarceloBravo/report-app-py.git levantada y
  configurada con `AI_SERVICE_BASE_URL=http://localhost:8000` (ver §6).

### 3.2 Servicio de IA — dos alternativas

La inferencia **no está dentro de este repositorio**: se delega a un servicio externo. Hay dos
opciones soportadas por el mismo adaptador (`OpenAILLMClient`, endpoint compatible con OpenAI).

#### Opción A — API comercial (requiere cuenta y credencial de pago)

| Proveedor | Requisito | Variables |
|---|---|---|
| **OpenAI** | API key (`https://platform.openai.com/api-keys`) | `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `LLM_MODEL=gpt-4o-mini-2024-07-18` |
| **Anthropic** | API key + `uv sync --extra anthropic` | `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL=claude-sonnet-4-20250514` |

Ventajas: máxima calidad y cero gestión de hardware. Coste por token, requiere salida a internet.

#### Opción B — Ollama autoalojado (opción usada en este proyecto)

**No requiere API key ni coste por token.** En este caso el servicio de IA está **levantado en otra
máquina** de la red local, no en la máquina que ejecuta FastAPI.

Requisitos de la máquina de IA:

- **Ollama instalado y en ejecución** (Linux / macOS / Windows / Docker).
- El modelo **`qwen2.5-coder:7b`** descargado: `ollama pull qwen2.5-coder:7b`
  (≈ 4,7 GB; renderizado por CPU es viable, pero lento → conviene subir `LLM_TIMEOUT_SECONDS`).
- **Ollama escuchando en la red, no solo en localhost.** Opcionalmente fijá la variable
  `OLLAMA_HOST=0.0.0.0:11434` y exponé el puerto 11434 en el firewall:

  ```bash
  # Linux (systemd)
  sudo systemctl edit ollama
  # -> [Service]
  # -> Environment="OLLAMA_HOST=0.0.0.0:11434"
  sudo systemctl restart ollama
  ```

- Verificación desde la máquina de FastAPI:
  `curl http://<IP-Ollama>:11434/v1/models`

Configuración correspondiente en `.env` (ver `.env` local de este repo, que apunta a `192.168.1.8`):

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5-coder:7b
OLLAMA_BASE_URL=http://192.168.1.8:11434/v1
LLM_TIMEOUT_SECONDS=180
LLM_MAX_TOKENS=1024
```

Notas:
- Ollama se consume por su endpoint **OpenAI-compatible** (`/v1`), de ahí que
  `OLLAMA_BASE_URL` termine en `/v1` y que no haga falta API key (el cliente envía un valor ficticio).
- Si `ai-service` corre en Docker y Ollama en el host: `LLM_BASE_URL=http://host.docker.internal:11434/v1`.
- GPU no obligatoria; con CPU conviene un modelo menor (`qwen2.5-coder:3b`) o más timeout.

---

## 4. Puesta en marcha (desarrollo local)

### 4.1 Con uv

```bash
# 1. Dependencias (crea .venv)
uv sync
#   Si vas a usar Anthropic: uv sync --extra anthropic

# 2. Configuración
cp .env.example .env       # editar según el proveedor elegido (§3.2)

# 3. Arrancar
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4.2 Con Docker

```bash
docker build -t ai-service .
docker run -d --name ai-service -p 8000:8000 --env-file .env ai-service
```

Si Ollama está en otra máquina, nada cambia: `OLLAMA_BASE_URL` ya apunta a su IP.
Si Ollama está en el host y `ai-service` en Docker, usá
`LLM_BASE_URL=http://host.docker.internal:11434/v1`.

### 4.3 Verificación

```bash
curl http://localhost:8000/health
# {"estado":"ok"}

# Swagger interactivo
# http://localhost:8000/docs
```

### 4.4 Calidad

```bash
uv run pytest           # tests (usan un LLM fake: no gastan tokens)
uv run ruff check .     # lint
```

Depuración: VS Code → *Run and Debug* → `AI Service: uvicorn (debug)`, o
`uv run uvicorn app.main:app --port 8000` y el launcher `AI Service: attach (5678)`.

---

## 5. Configuración

| Variable | Default | Descripción |
|---|---|---|
| `SERVICE_PORT` | `8000` | Puerto del servicio |
| `LLM_PROVIDER` | `openai` | Proveedor: `openai` \| `anthropic` \| `ollama` |
| `LLM_MODEL` | `gpt-4o-mini-2024-07-18` | Modelo por defecto |
| `LLM_BASE_URL` | — | URL base opcional (compatible con OpenAI); tiene prioridad sobre `OLLAMA_BASE_URL` |
| `OPENAI_API_KEY` | — | Credencial OpenAI (o valor ficticio con Ollama) |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Endpoint OpenAI-compatible de Ollama |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | — / `claude-sonnet-4-20250514` | Credencial y modelo Anthropic |
| `LLM_TIMEOUT_SECONDS` | `30` | Timeout de la llamada al LLM (subir a 120-180 con CPU) |
| `LLM_MAX_TOKENS` | `2048` | Máximo de tokens de la respuesta |
| `LLM_REVISAR_FK` | `true` | 2.ª pasada de revisión/corrección de JOINs por claves foráneas (llamada extra al LLM, solo si el esquema tiene FKs) |
| `MAX_SCHEMA_TABLES` / `MAX_SCHEMA_COLUMNS` | `50` / `200` | Límites del esquema (se trunca y se avisa al LLM) |
| `MAX_PROMPT_CHARS` | `8000` | Límite de caracteres del prompt final |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:8080` | Orígenes CORS permitidos (lista separada por comas) |

`.env` está en `.gitignore`: **nunca subas credenciales**.

---

## 6. Aplicación consumidora (Spring Boot)

- **Repositorio:** https://github.com/MarceloBravo/report-app-py.git
- Contrato: Spring Boot envía `POST {AI_SERVICE_BASE_URL}/sql` con
  `{ tenantId, usuarioId, preguntaUsuario, esquema }` y recibe `{ tenantId, querySql, exitosa, tiempoMs }`.
- Configuración típica en la app Spring Boot:

  ```properties
  AI_SERVICE_BASE_URL=http://localhost:8000
  ```

- Spring Boot **re-valida** el SQL recibido (solo `SELECT`, sin `;`, sin comentarios, tablas
  permitidas) antes de ejecutarlo contra PostgreSQL, aplica límites de plan y persiste el historial.
- El usuario nunca llama directamente a `ai-service`: expone su propio `POST /consultas`.
- `CORS_ALLOWED_ORIGINS` debe incluir el origen del frontend Spring Boot (por defecto `http://localhost:8080`).

---

## 7. Estructura de archivos

```
ai-service/
├── app/
│   ├── main.py                      # FastAPI app (POST /sql, GET /health)
│   ├── config.py                    # Settings desde variables de entorno
│   ├── api/                         # Capa de presentación (schemas + errores HTTP)
│   ├── application/                 # Capa de aplicación (caso de uso)
│   ├── domain/                      # Dominio puro (prompt, esquema, guardrails)
│   └── infrastructure/llm/          # Adaptadores del proveedor de IA (puerto + impls)
├── tests/                           # pytest con LLM fake (sin coste de API)
├── .env.example                     # Plantilla de configuración
├── Dockerfile                       # python:3.12-slim + uv
├── pyproject.toml
└── uv.lock
```
