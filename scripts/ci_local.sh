#!/usr/bin/env bash
# Rulează pytest + dependențe dev (echivalent cu job-ul local din CI-ul monorepo-ului, dacă îl folosești).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export LLM_MODE="${LLM_MODE:-disabled}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-test-key-ci-local}"
pip install -q -r requirements-dev.txt
pytest tests/ -q --tb=short
# E2E Playwright (separat): bash scripts/e2e_playwright.sh
