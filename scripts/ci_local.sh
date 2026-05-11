#!/usr/bin/env bash
# Rulează pytest fără Playwright (același lucru ca job-ul pytest-unit din .github/workflows/ci.yml).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export LLM_MODE="${LLM_MODE:-disabled}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-test-key-ci-local}"
export ANONYMIZED_TELEMETRY="${ANONYMIZED_TELEMETRY:-False}"
pip install -q -r requirements-dev.txt
pytest tests/ -q --tb=short --ignore=tests/e2e
# E2E Playwright (job separat în CI): bash scripts/e2e_playwright.sh
