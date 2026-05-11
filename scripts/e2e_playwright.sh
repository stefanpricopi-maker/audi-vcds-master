#!/usr/bin/env bash
# Rulează testele Playwright (E2E) împotriva unui uvicorn local.
# Folosește PLAYWRIGHT_BROWSERS_PATH în proiect ca instalarea browserelor să fie reproductibilă.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$ROOT/.pw-browsers}"
export LLM_MODE="${LLM_MODE:-disabled}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-test-key-e2e}"
pip install -q -r requirements-dev.txt
python -m playwright install chromium
export E2E=1
pytest tests/e2e "$@"
