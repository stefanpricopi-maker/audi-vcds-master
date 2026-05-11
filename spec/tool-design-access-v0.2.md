# Tool Design — Loguri VCDS, upload, MCP & HTTP

## Version History
| Version | Date | Author | Changes |
|---|---|---|---|
| 0.1 | 2026-05-11 | Cursor Agent + Stefan | Draft inițial: `vcds_read_latest_log` |
| 0.2 | 2026-05-11 | Cursor Agent + Stefan | MCP server, `vcds_get_context`, paritate HTTP (`/vcds-context`, `/uploaded-context`), modul partajat `app/vcds_context.py` |
| 0.3 | 2026-05-11 | Cursor Agent + Stefan | Fișier canonical redenumit: `tool-design-vcds_read_latest_log-v0.1.md` → `tool-design-access-v0.2.md` (stub la vechiul nume) |
| 0.4 | 2026-05-11 | Cursor Agent + Stefan | Clarificat: MCP + HTTP pe același mediu local, fără model de serviciu pentru terți |

## 1. Scop
Documentează **accesul read-only la loguri** (VCDS pe disk + loguri încărcate manual) astfel cum e implementat în proiect: **MCP** (ex. integrare Cursor pe același calculator) și **HTTP** (API + UI locală, același comportament).

## 2. Surse de date
| Sursă | Config | Cod |
|---|---|---|
| Folder VCDS (Ross-Tech etc.) | `VCDS_LOG_DIR` | `app/vcds_logs.py`, `app/vcds_context.py` |
| Loguri încărcate (test / fără VCDS) | `UPLOADED_LOGS_DIR` | `app/uploaded_logs.py`, `app/uploaded_context.py` |

Fișiere considerate “log VCDS” în folderul VCDS: extensii **`.csv`**, **`.txt`**, **`.log`**. În `UPLOADED_LOGS_DIR` se acceptă **orice fișier** (upload manual).

## 3. MCP server (`mcp_server/server.py`)
Transport: **stdio**. Rulează: `python -m mcp_server.server` din `projects/audi-vcds-master`, cu `VCDS_LOG_DIR` setat (sau în `.env`).

| Tool | Rol | Parametri notabili | Răspuns |
|---|---|---|---|
| **`vcds_get_context`** | Recomandat: listă scurtă + conținut log (ultimul sau explicit) | `path` opțional, `recent_limit` (1–100), `max_bytes` (cap 2MB) | JSON string: `ok`, `base`, `recent_files`, `selection`, `log` sau `read_error` |
| `vcds_list_logs` | Doar listă fișiere | `limit` (1–200) | JSON string |
| `vcds_read_latest_log` | Doar ultimul fișier | `max_bytes` | JSON string |
| `vcds_read_log` | Un fișier după path absolut | `path`, `max_bytes` | JSON string |

**Paritate logică:** `vcds_get_context` apelează `build_vcds_context()` din `app/vcds_context.py` (aceeași funcție ca endpoint-ul HTTP).

### 3.1 Securitate MCP
- Citește **doar** fișiere sub `VCDS_LOG_DIR` (path absolut verificat cu `safe_log_file_under_dir`).
- Read-only: nu scrie în `VCDS_LOG_DIR`.
- Date **untrusted**: același tratament ca în system prompt (nu instrucțiuni).

### 3.2 Erori uzuale
- `VCDS_LOG_DIR is not set`
- `log_dir_missing` — calea nu există sau nu e director
- `no_logs_found` / lipsă fișiere — la citire: `log: null`, `read_error` în snapshot

## 4. HTTP — snapshot (paritate cu `vcds_get_context`)
| Endpoint | Config | Comportament |
|---|---|---|
| `GET /vcds-context` | `VCDS_LOG_DIR` | Același payload ca `vcds_get_context` (dict JSON, nu string) |
| `GET /uploaded-context` | `UPLOADED_LOGS_DIR` | Aceeași formă: `recent_files` + `log` / `read_error` |

Query params comuni: `path` (opțional), `recent_limit`, `max_bytes`.

## 5. HTTP — alte endpoint-uri relevante (rezumat)
Nu sunt “tool-uri MCP”, dar fac parte din același agent runtime:
- `POST /upload-log`, `GET /logs`, `GET /analyze-*`, `GET /report-*`, `GET /report-case*`, `GET /log-raw`
- `GET /search`, `POST /ingest-text`, `POST /ingest-files` (RAG; PDF fără OCR pentru scanări)
- `GET /status`, `GET /health`, UI la `GET /`

## 6. Tool istoric: `vcds_read_latest_log` (concept)
**Nume:** `vcds_read_latest_log`  
**Descriere:** Citește cel mai recent fișier de log din `VCDS_LOG_DIR`; returnează `path`, `mtime`, `csv_text`.  
**Implementare:** echivalentă cu ramura `selection: "latest"` din `vcds_get_context` / `build_vcds_context` (fără lista `recent_files`), și cu `vcds_read_latest_log` din MCP.

## 7. Parametri & limite
- `max_bytes` efectiv plafonat la **2_000_000** în MCP și în `build_vcds_context` / `build_uploaded_context`.
- Decodare text: UTF-8 cu fallback **latin-1** + `replace` (vezi `app/vcds_logs.py`, `app/uploaded_logs.py`).

## 8. Least privilege
| Zonă | Permisiuni |
|---|---|
| `VCDS_LOG_DIR` | Read-only |
| `UPLOADED_LOGS_DIR` | Read pentru analiză; **scriere** doar prin `POST /upload-log` (nu prin MCP) |
| `INGEST_UPLOADS_DIR` | Scriere la `POST /ingest-files` (copie fișier + index RAG) |

## 9. Security note (neschimbat față de v0.1)
- **Untrusted data** în loguri și în fragmentele RAG.
- **Injection:** conținutul rămâne date delimitate în prompt; teste adversariale în `test-plan-v0.1.md`.

## 10. Cost note
- Citire disk: neglijabil.
- Tokeni LLM: crește cu mărimea `csv_text`; folosește `vcds_get_context` / snapshot-uri cu `max_bytes` rezonabil.
