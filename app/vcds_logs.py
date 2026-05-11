from __future__ import annotations

from pathlib import Path
from typing import Any


def _is_vcds_log(path: Path) -> bool:
    name = path.name.lower()
    return path.is_file() and (name.endswith(".csv") or name.endswith(".txt") or name.endswith(".log"))


def list_vcds_logs(log_dir: Path) -> list[Path]:
    if not log_dir.exists() or not log_dir.is_dir():
        return []
    return sorted([p for p in log_dir.iterdir() if _is_vcds_log(p)], key=lambda p: p.stat().st_mtime, reverse=True)


def read_vcds_log(path: Path, *, max_bytes: int = 400_000) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raw = raw[-max_bytes:]

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")

    return {"path": str(path), "mtime": path.stat().st_mtime, "csv_text": text}


def read_latest_vcds_log(log_dir: Path, *, max_bytes: int = 250_000) -> dict[str, Any]:
    if not log_dir.exists() or not log_dir.is_dir():
        raise FileNotFoundError(f"VCDS log dir not found or not a directory: {log_dir}")

    candidates = [p for p in log_dir.iterdir() if _is_vcds_log(p)]
    if not candidates:
        raise FileNotFoundError(f"No VCDS log files found in: {log_dir}")

    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return read_vcds_log(latest, max_bytes=max_bytes)

