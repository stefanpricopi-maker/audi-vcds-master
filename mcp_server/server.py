"""
Audi VCDS Master — MCP server (read-only VCDS logs).

Pentru uz local (ex. Cursor pe același PC). Nu expune un model de serviciu multi-client.

Run from project root (projects/audi-vcds-master):

    export VCDS_LOG_DIR="/path/to/VCDS/Logs"
    python -m mcp_server.server

Or configure `VCDS_LOG_DIR` in `.env` next to this package.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.vcds_context import build_vcds_context, safe_log_file_under_dir  # noqa: E402
from app.vcds_logs import list_vcds_logs, read_latest_vcds_log, read_vcds_log  # noqa: E402

mcp = FastMCP("audi-vcds-logs")


def _log_base() -> Path | None:
    raw = (os.getenv("VCDS_LOG_DIR") or "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


@mcp.tool()
def vcds_get_context(
    path: str | None = None,
    recent_limit: int = 15,
    max_bytes: int = 250_000,
) -> str:
    """
    Recommended default: recent VCDS logs (names + mtimes) plus full text of the newest log,
    or of a specific file if `path` is set (absolute path, must stay under VCDS_LOG_DIR).
    One call instead of list + read. Read-only.
    """
    payload = build_vcds_context(
        os.getenv("VCDS_LOG_DIR"),
        explicit_path=path,
        recent_limit=recent_limit,
        max_bytes=max_bytes,
    )
    return json.dumps(payload, ensure_ascii=False)


@mcp.tool()
def vcds_list_logs(limit: int = 30) -> str:
    """List VCDS log files (.csv, .txt, .log) in VCDS_LOG_DIR, newest first. Read-only."""
    base = _log_base()
    if base is None:
        return json.dumps({"ok": False, "error": "VCDS_LOG_DIR is not set"}, ensure_ascii=False)

    if limit < 1 or limit > 200:
        return json.dumps({"ok": False, "error": "limit must be 1..200"}, ensure_ascii=False)

    if not base.exists() or not base.is_dir():
        return json.dumps(
            {"ok": False, "error": f"log_dir_missing: {base}", "code": "log_dir_missing"},
            ensure_ascii=False,
        )

    files = list_vcds_logs(base)[:limit]
    items = [
        {"path": str(p), "name": p.name, "mtime": p.stat().st_mtime}
        for p in files
    ]
    return json.dumps({"ok": True, "base": str(base), "count": len(items), "items": items}, ensure_ascii=False)


@mcp.tool()
def vcds_read_latest_log(max_bytes: int = 250_000) -> str:
    """Read the newest VCDS log in VCDS_LOG_DIR. Returns path, mtime, and text (truncated if large). Read-only."""
    base = _log_base()
    if base is None:
        return json.dumps({"ok": False, "error": "VCDS_LOG_DIR is not set"}, ensure_ascii=False)

    cap = min(max(1, max_bytes), 2_000_000)
    try:
        data = read_latest_vcds_log(base, max_bytes=cap)
    except FileNotFoundError as e:
        return json.dumps({"ok": False, "error": str(e), "code": "no_logs_or_dir"}, ensure_ascii=False)

    return json.dumps({"ok": True, **data}, ensure_ascii=False)


@mcp.tool()
def vcds_read_log(path: str, max_bytes: int = 400_000) -> str:
    """Read one VCDS log file by absolute path. Path must be inside VCDS_LOG_DIR. Read-only."""
    base = _log_base()
    if base is None:
        return json.dumps({"ok": False, "error": "VCDS_LOG_DIR is not set"}, ensure_ascii=False)

    cap = min(max(1, max_bytes), 2_000_000)
    try:
        p = safe_log_file_under_dir(base, path)
    except (OSError, ValueError, FileNotFoundError, PermissionError) as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    data = read_vcds_log(p, max_bytes=cap)
    return json.dumps({"ok": True, **data}, ensure_ascii=False)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
