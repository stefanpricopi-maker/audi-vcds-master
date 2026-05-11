"""
Snapshot for manually uploaded logs directory (same shape as vcds_context).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.uploaded_logs import list_uploaded_logs, read_latest_uploaded_log, read_uploaded_log
from app.vcds_context import safe_log_file_under_dir


def build_uploaded_context(
    upload_dir: str | Path | None,
    *,
    explicit_path: str | None = None,
    recent_limit: int = 15,
    max_bytes: int = 250_000,
) -> dict[str, Any]:
    if upload_dir is None:
        return {"ok": False, "error": "upload_dir is not configured"}

    base = Path(upload_dir).expanduser().resolve()

    if not base.exists() or not base.is_dir():
        return {
            "ok": False,
            "error": f"upload_dir_missing: {base}",
            "code": "upload_dir_missing",
        }

    if recent_limit < 1 or recent_limit > 100:
        return {"ok": False, "error": "recent_limit must be 1..100"}

    cap = min(max(1, max_bytes), 2_000_000)
    all_logs = list_uploaded_logs(base)
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
            payload["log"] = read_uploaded_log(p, max_bytes=cap)
        else:
            payload["log"] = read_latest_uploaded_log(base, max_bytes=cap)
    except (OSError, ValueError, FileNotFoundError, PermissionError) as e:
        payload["log"] = None
        payload["read_error"] = str(e)

    return payload
