# Architecture Design — Audi VCDS Master

## Version History
| Version | Date | Author | Changes |
|---|---|---|---|
| 0.1 | 2026-05-11 | Cursor Agent + Stefan | Initial draft from kit |
| 0.2 | 2026-05-11 | Cursor Agent + Stefan | MCP server, snapshot HTTP, upload/ingest, UI static, `LLM_MODE`, variabile noi în `.env.example` |
| 0.3 | 2026-05-11 | Cursor Agent + Stefan | OpenAPI tags (`meta` / `chat` / `knowledge` / `logs`); Makefile pentru `run` / `test` / `ci` / `ingest` |
| 0.4 | 2026-05-11 | Cursor Agent + Stefan | `Dockerfile` + `.dockerignore` pentru rulare containerizată; `make docker-build` |
| 0.5 | 2026-05-11 | Cursor Agent + Stefan | Deployment doar local; eliminat limbaj de producție multi-utilizator |

## 0. Scope utilizare
Rulezi serviciul **doar pentru tine**, pe propriul echipament (de obicei `127.0.0.1`). Nu se specifică aici auth multi-utilizator, rate limiting pentru terți sau expunere pe internet.

## 1. Pattern
| Field | Value |
|---|---|
| **Pattern** | Orchestrator-Workers |
| **Justification** | Alternăm între “ground truth” (citire log) și “knowledge” (RAG), apoi sinteză. |
| **Architectural consequence** | Un endpoint `POST /chat` care poate (opțional) atașa latest log + retrieval chunks; răspunsul se generează într-un singur call LLM cu contextul agregat. |

**Matches agent definition Section 1:** Yes

## 2. Deployment (local)
| Field | Value |
|---|---|
| **Platform** | Local (laptop / desktop) |
| **Cod** | Monorepo `agent-builder`, subfolder `projects/audi-vcds-master` |
| **URL implicit** | `http://127.0.0.1:8088` (doar mașina ta) |
| **Port** | `8088` (configurabil la pornirea uvicorn) |
| **Concurrency model** | FastAPI + uvicorn; un singur operator, fără cerințe de scalare pentru mulți clienți |
| **Stateless / stateful** | Stateless (RAG index persistat pe disc; sesiunea nu se păstrează server-side) |
| **Runtime** | Python |
| **MCP** | Proces separat: `python -m mcp_server.server` (stdio), read-only pe `VCDS_LOG_DIR` — vezi `spec/tool-design-access-v0.2.md` |

### Environment variables (v0.2)
| Variable name | Description | Source | Required / Optional |
|---|---|---|---|
| `OPENAI_API_KEY` | Cheie API OpenAI | `.env` local | Required dacă `LLM_MODE=openai` |
| `OPENAI_MODEL` | Model | `.env` local | Optional |
| `LLM_MODE` | `openai` sau `disabled` (fallback fără apel model) | `.env` local | Optional |
| `MANUALS_DIR` | Folder PDF-uri | `.env` local | Optional |
| `PUBLIC_NOTES_DIR` | Note markdown versionate în repo (`knowledge/public`), folosite la ingest script | `.env` / script | Optional |
| `VECTORSTORE_DIR` | Folder index RAG | `.env` local | Optional |
| `VCDS_LOG_DIR` | Folder loguri VCDS | `.env` local | Optional (obligatoriu pentru `/vcds-context`, `source=vcds`, MCP) |
| `UPLOADED_LOGS_DIR` | Loguri încărcate manual | `.env` local | Optional |
| `INGEST_UPLOADS_DIR` | Copii fișiere `POST /ingest-files` | `.env` local | Optional |
| `MAX_CONTEXT_CHUNKS` | câte chunks injectăm | `.env` local | Optional |

## 3. API contract (v0.2)
### `POST /chat`
- **Request**: `{ "message": string, "include_latest_vcds_log": boolean, "include_latest_uploaded_log": boolean, "include_vcds_snapshot": boolean, "include_uploaded_snapshot": boolean, "vcds_snapshot_path": string | null, "uploaded_snapshot_path": string | null }`
- **Response**: `{ "answer": string, "used_manual_chunks": [...], "used_latest_vcds_log": {path, mtime} | null }` (câmpul poartă numele istoric; conținutul poate veni din log încărcat când ultimul context e setat astfel în cod.)

### `GET /health`
Returnează `{status, version}`.

### `GET /status`
Diagnostic setup: mod LLM, căi, existență directoare, `rag_chunks`, număr loguri upload / VCDS.

### Snapshot loguri (paritate cu MCP `vcds_get_context`)
- **`GET /vcds-context`** — `build_vcds_context(VCDS_LOG_DIR, …)` → `recent_files` + `log` (+ `read_error` dacă e cazul).
- **`GET /uploaded-context`** — `build_uploaded_context(UPLOADED_LOGS_DIR, …)` — aceeași formă a JSON-ului.

### RAG & ingest
- `GET /search`, `POST /ingest-text`, `POST /ingest-files` (`.pdf`/`.md`/`.txt`; PDF scanat fără text rămâne fără OCR în v0.2).

### Loguri & rapoarte (extras față de v0.1)
- `POST /upload-log`, `GET /logs`, `GET /analyze-latest-log`, `GET /analyze-log`, `GET /log-raw`
- `GET /report-latest-log`, `GET /report-log`, `GET /report-log.md`, `GET /report-case`, `GET /report-case-from`

### UI
- `GET /` servește `static/index.html`; asseturi sub `/static/`.

### OpenAPI (`/docs`, `/openapi.json`)
- Rute grupate pe tag-uri: **meta**, **chat**, **knowledge**, **logs** (pentru navigare în Swagger UI).

### Container (Docker, opțional)
- `Dockerfile` în `projects/audi-vcds-master` (Python 3.12-slim, `libgomp1`, user non-root `app`) — folositor când ai Docker; dezvoltarea locală standard rămâne **venv + uvicorn**.
- Date persistente: montări recomandate pentru `data/vectorstore`, `data/uploaded-logs`, opțional `data/manuals`.

## 4. Data schema
v0.1: nu persistă conținutul conversației; indexul RAG este persistat în `VECTORSTORE_DIR`.

## 5. Workflow (v0.2)
1. Validează input.
2. Dacă `include_latest_vcds_log=true`, citește latest log din `VCDS_LOG_DIR` (read-only). Dacă `include_latest_uploaded_log=true`, citește ultimul fișier din `UPLOADED_LOGS_DIR`.
3. Rulează retrieval pe vector store pentru `message` (și eventual query suplimentar în mod fallback).
4. Construiește context delimitat: `<vcds_csv>...</vcds_csv>` și `<docs>...</docs>`.
5. Dacă `LLM_MODE=openai`: un call la model. Dacă `disabled`: răspuns determinist din parsere + pași + referințe din index.

## 6. Error handling (v0.2)
- `400`: lipsă `VCDS_LOG_DIR` când se cere log VCDS; parametri invalizi; upload gol
- `403` / `404`: path în afara directorului permis (analyze/report/log-raw pe fișier)
- `413`: fișier prea mare la `ingest-files`
- `500`: eșec LLM / răspuns gol

## 7. Observability (v0.1)
- Logging minimal (stdout), suficient pentru depanare locală. Opțional: urmărire token/latency pentru bugetul tău API.

## 8. Security (v0.2)
- **Input trust model**: PDF-urile și logurile sunt tratate ca **untrusted data**.
- Delimitare structurală în prompt (`<vcds_csv>`, `<docs>`).
- Acces la fișiere: read-only în folderele configurate; path-uri pentru analyze/report validate sub `UPLOADED_LOGS_DIR` sau `VCDS_LOG_DIR`.
- **MCP**: același model de încredere — doar citire sub `VCDS_LOG_DIR`.

## 9. Tech stack mapping
| Component | Layer | Platform / Tool | Rationale |
|---|---|---|---|
| API server | Application | FastAPI | Rapid local service |
| Retrieval | Application | Chroma local persistent | Setup simplu, local |
| PDF extraction | Scripts | pypdf | Extrage text per pagină |
| LLM | External | OpenAI | Model runtime |

## 10. Prompt source
v0.1: prompturile sunt in-code (constante în `app/main.py`).

## 11. RAI considerations (v0.1)
- Data minimization: nu persistăm loguri brute; doar citim și procesăm în memorie.
- Kill switch: oprirea serverului local.

## 12. Deviations
Față de draft-ul v0.1 (“MCP în v2”): **MCP pentru loguri VCDS e livrat în v0.2**, în paralel cu HTTP. OCR pentru PDF-uri scanate rămâne în afara scope-ului curent (vezi README).

