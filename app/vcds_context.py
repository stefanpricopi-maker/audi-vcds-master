"""
Shared VCDS "snapshot" for HTTP API and MCP: recent files + one log body.
Read-only; paths must stay under the configured log directory.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.vcds_logs import list_vcds_logs, read_latest_vcds_log, read_vcds_log


def _is_under_base(base: Path, candidate: Path) -> bool:
    try:
        return candidate.is_relative_to(base)
    except AttributeError:
        return str(candidate).startswith(str(base) + os.sep)


def safe_log_file_under_dir(base: Path, path_str: str) -> Path:
    if not path_str.strip():
        raise ValueError("path is empty")
    p = Path(path_str).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Not a file: {path_str}")
    if not _is_under_base(base, p):
        raise PermissionError("path must be inside the configured VCDS log directory")
    return p


def build_vcds_context(
    log_dir: str | Path | None,
    *,
    explicit_path: str | None = None,
    recent_limit: int = 15,
    max_bytes: int = 250_000,
) -> dict[str, Any]:
    """
    Return a dict suitable for JSON (MCP string or FastAPI response).

    Keys: ok, base?, recent_files?, selection?, log?, read_error?
    """
    raw = ""
    if log_dir is None:
        raw = ""
    elif isinstance(log_dir, Path):
        raw = str(log_dir)
    else:
        raw = (log_dir or "").strip()

    if not raw:
        return {"ok": False, "error": "VCDS_LOG_DIR is not set"}

    base = Path(raw).expanduser().resolve()

    if not base.exists() or not base.is_dir():
        return {
            "ok": False,
            "error": f"log_dir_missing: {base}",
            "code": "log_dir_missing",
        }

    if recent_limit < 1 or recent_limit > 100:
        return {"ok": False, "error": "recent_limit must be 1..100"}

    cap = min(max(1, max_bytes), 2_000_000)
    all_logs = list_vcds_logs(base)
    recent = [
        {"path": str(p), "name": p.name, "mtime": p.stat().st_mtime}
        for p in all_logs[:recent_limit]
    ]

    path = (explicit_path or "").strip()
    payload: dict[str, Any] = {
        "ok": True,
        "base": str(base),
        "recent_files": recent,
        "selection": "explicit" if path else "latest",
    }

    try:
        if path:
            p = safe_log_file_under_dir(base, path)
            payload["log"] = read_vcds_log(p, max_bytes=cap)
        else:
            payload["log"] = read_latest_vcds_log(base, max_bytes=cap)
    except (OSError, ValueError, FileNotFoundError, PermissionError) as e:
        payload["log"] = None
        payload["read_error"] = str(e)

    return payload
