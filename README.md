## Audi VCDS Master (RAG + local logs)

**Uz:** personal, pe propriul calculator (de obicei `127.0.0.1`). Nu este descris aici ca produs pentru terți sau serviciu găzduit.

Un agent local pentru Audi A4 B7 care:
- **știe** din documentație (manuale Haynes/Bentley, scheme electrice, PDF-uri) prin **RAG**.
- **acționează** citind loguri VCDS dintr-un folder local (în prima iterație: direct din filesystem; ulterior: printr-un server **MCP** dedicat).

### Ce conține folderul
- `spec/`: documentele de specificație (agent definition, architecture, tool design, system prompt, test plan)
- `app/`: serviciu minimal (FastAPI) pentru chat + retrieval + citire loguri
- `scripts/`: ingestie PDF-uri în vector store
- `data/manuals/`: pui PDF-urile aici (nu se comite în git)
- `data/vectorstore/`: vector store local (persistență)

### Quick start (local)
1) Pune PDF-urile în `data/manuals/`.

2) Configurează environment:

```bash
cd projects/audi-vcds-master
cp .env.example .env
```

3) Instalează dependențe:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4) Ingest PDF-urile (creează/actualizează indexul local):

```bash
python scripts/ingest_manuals.py
```

5) Pornește API-ul:

```bash
uvicorn app.main:app --reload --port 8088
```

6) Deschide UI-ul:

- `http://127.0.0.1:8088/`

### Teste automate (pytest)

```bash
pip install -r requirements-dev.txt
pytest tests/
```

Playwright (UI): după `python -m playwright install chromium` (sau `bash scripts/e2e_playwright.sh` care setează `PLAYWRIGHT_BROWSERS_PATH` în `.pw-browsers/`), rulează `E2E=1 pytest tests/e2e` sau tot pachetul cu `E2E=1 pytest tests/`.

Sau din același folder:

```bash
bash scripts/ci_local.sh
```

Cu **Make**: `make test`, `make ci`, `make run` (uvicorn pe 8088), `make ingest`.

### Docker (opțional)
Dacă **nu** ai Docker instalat, poți ignora complet această secțiune; API-ul rulează normal cu Python + venv. `Dockerfile` rămâne în proiect pentru mai târziu (`make docker-build` când ai Docker).

```bash
docker build -t audi-vcds-master .
docker run --rm -p 8088:8088 -e LLM_MODE=disabled \
  -v "$(pwd)/data/vectorstore:/app/data/vectorstore" \
  -v "$(pwd)/data/uploaded-logs:/app/data/uploaded-logs" \
  audi-vcds-master
```

Apoi: `http://127.0.0.1:8088/` și `/docs`. Pentru manuale PDF, montează și `data/manuals` sau rulează ingest în container.

Pe GitHub: workflow **CI** (`.github/workflows/ci.yml`) — la fiecare push/PR: job **pytest-unit** (`pytest … --ignore=tests/e2e`) și **playwright-e2e** (trace/video la eșec; artifact **`playwright-e2e-failure`** → `test-results/`). Local: `bash scripts/ci_local.sh` / `bash scripts/e2e_playwright.sh`.

**Dependabot:** `.github/dependabot.yml` — `pip` și `github-actions` la rădăcina acestui repo.

**Observabilitate:** fiecare `POST /chat` scrie o linie JSON în logger-ul `audi_vcds.chat` (lungime mesaj, bifări context, `llm_mode`) — fără conținutul mesajului. Activează nivel `INFO` pentru logger sau root ca să o vezi în consolă / agregator.

**PDF:** nu există generare PDF pe server (fără dependențe suplimentare de layout); folosește butoanele de print din UI și **Print → Save as PDF** în browser.

7) Exemplu request:

```bash
curl -s http://127.0.0.1:8088/chat \
  -H 'content-type: application/json' \
  -d '{"message":"Tocmai am facut o scanare, vezi ce a aparut nou."}'
```

### Test fără VCDS instalat (upload log)
1) Încarcă un fișier `.CSV` / `.LOG`:

```bash
curl -s http://127.0.0.1:8088/upload-log \
  -F "file=@/path/to/your/log.csv"
```

2) Cere agentului să folosească ultimul log încărcat:

```bash
curl -s http://127.0.0.1:8088/chat \
  -H 'content-type: application/json' \
  -d '{"message":"Tocmai am facut o scanare, vezi ce a aparut nou.","include_latest_uploaded_log":true}'
```

3) Chat cu **snapshot complet** (listă recentă + log, ca `/uploaded-context` / `/vcds-context`), fără să repeți doar ultimul CSV:

```bash
curl -s http://127.0.0.1:8088/chat \
  -H 'content-type: application/json' \
  -d '{"message":"Ce fișiere recente vezi și ce conține ultimul log?","include_uploaded_snapshot":true}'
```

Poți trimite și **`uploaded_snapshot_path`** / **`vcds_snapshot_path`** (path absolut, în directorul permis) ca să forțezi un fișier anume în snapshot, nu doar „latest”.

### Snapshot VCDS (HTTP, același ca MCP `vcds_get_context`)
Dacă `VCDS_LOG_DIR` e setat, poți lua într-un singur request lista scurtă + conținutul ultimului log (sau al unui fișier dat):

```bash
curl -s "http://127.0.0.1:8088/vcds-context?recent_limit=15&max_bytes=250000"
curl -s "http://127.0.0.1:8088/vcds-context?path=/ABS/PATH/TO/file.csv&recent_limit=10"
```

### Snapshot loguri încărcate (`/uploaded-context`)
Același format ca `/vcds-context`, dar pentru `UPLOADED_LOGS_DIR` (upload prin UI sau `POST /upload-log`):

```bash
curl -s "http://127.0.0.1:8088/uploaded-context?recent_limit=15&max_bytes=250000"
```

### Căutare RAG fără LLM (`/search`)
După ce rulezi `python scripts/ingest_manuals.py`, poți interoga direct indexul:

```bash
curl -s "http://127.0.0.1:8088/search?q=P0299%20underboost%20N75%20vacuum&k=6"
```

### Ingest din UI (`POST /ingest-files`)
Poți urca direct din interfață fișiere **`.pdf`**, **`.md`**, **`.txt`**; sunt salvate în `INGEST_UPLOADS_DIR` (implicit `data/ingested-uploads/`) și indexate în RAG. PDF-urile cu text selectabil merg bine; **PDF-uri scanate (imagini)** pot să nu aibă text extras până când adăugăm OCR (lăsat pentru final).

```bash
curl -s http://127.0.0.1:8088/ingest-files \
  -F "files=@/path/to/manual.pdf"
```

### MCP server (citire loguri VCDS, read-only)
În `audi-vcds-master` există un server MCP separat care expune tool-uri pentru folderul `VCDS_LOG_DIR` (doar `.csv` / `.txt` / `.log`), fără scriere pe disk.

**Instalare** (aceleași dependențe ca API-ul; include pachetul `mcp`):

```bash
pip install -r requirements.txt
```

**Rulare manuală** (stdio — de ex. integrare **Cursor** cu protocol MCP pe același PC):

```bash
cd projects/audi-vcds-master
export VCDS_LOG_DIR="/path/to/VCDS/Logs"   # ex. Windows în VM: C:\\Ross-Tech\\VCDS\\Logs
python -m mcp_server.server
```

**Tool-uri** (începe cu primul; restul sunt pentru cazuri fine):
- **`vcds_get_context`** — recomandat: ultimele loguri (metadate) + textul complet al celui mai nou log, sau al fișierului indicat prin `path` (absolut, sub `VCDS_LOG_DIR`)
- `vcds_list_logs` — doar listă
- `vcds_read_latest_log` — doar ultimul fișier
- `vcds_read_log` — un fișier după path absolut

**Cursor (exemplu `mcp.json`)** — adaptează `cwd` la calea ta absolută:

```json
{
  "mcpServers": {
    "audi-vcds-logs": {
      "command": "python3",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/Users/YOU/dev/agent-builder/projects/audi-vcds-master",
      "env": {
        "VCDS_LOG_DIR": "/path/to/VCDS/Logs"
      }
    }
  }
}
```

Dacă folosești venv: pune în `command` calea către `.../audi-vcds-master/.venv/bin/python` în loc de `python3`.

### Notă despre MCP vs API
API-ul FastAPI poate citi tot `VCDS_LOG_DIR` când `source=vcds`. Serverul MCP oferă același tip de acces **read-only** la loguri prin protocol MCP (ex. din Cursor), fără să folosești endpoint-urile HTTP pentru acel flux.

