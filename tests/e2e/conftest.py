from __future__ import annotations

"""Playwright E2E: pornește uvicorn local. Rulează cu E2E=1.

Browsere: export PLAYWRIGHT_BROWSERS_PATH=\"$PWD/.pw-browsers\" apoi
``python -m playwright install chromium``, sau ``bash scripts/e2e_playwright.sh``.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]

_default_pw = _ROOT / ".pw-browsers"
if not os.environ.get("PLAYWRIGHT_BROWSERS_PATH") and _default_pw.is_dir():
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_default_pw)


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
def e2e_server() -> str:
    port = _pick_free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 90
    last_err: Exception | None = None
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"uvicorn exited early (code {proc.returncode}); check app startup locally")
        try:
            urllib.request.urlopen(base + "/health", timeout=2)
            break
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            time.sleep(0.25)
    else:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise RuntimeError(f"server did not become ready at {base}: {last_err!r}")

    yield base

    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def base_url(e2e_server: str) -> str:
    return e2e_server
