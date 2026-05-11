from __future__ import annotations

import time
from pathlib import Path
from typing import Any


def ensure_upload_dir(base_dir: Path) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def save_uploaded_log(upload_dir: Path, *, filename: str, content: bytes) -> dict[str, Any]:
    upload_dir = ensure_upload_dir(upload_dir)
    safe_name = "".join(c for c in filename if c.isalnum() or c in ("-", "_", ".", " ")).strip()
    if not safe_name:
        safe_name = "vcds-log.csv"

    ts = time.strftime("%Y%m%d-%H%M%S")
    path = upload_dir / f"{ts}__{safe_name}"
    path.write_bytes(content)
    return {"path": str(path), "mtime": path.stat().st_mtime}


def read_latest_uploaded_log(upload_dir: Path, *, max_bytes: int = 250_000) -> dict[str, Any]:
    if not upload_dir.exists() or not upload_dir.is_dir():
        raise FileNotFoundError(f"Upload dir not found or not a directory: {upload_dir}")

    files = [p for p in upload_dir.iterdir() if p.is_file()]
    if not files:
        raise FileNotFoundError(f"No uploaded logs found in: {upload_dir}")

    latest = max(files, key=lambda p: p.stat().st_mtime)
    raw = latest.read_bytes()
    if len(raw) > max_bytes:
        raw = raw[-max_bytes:]

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")

    return {"path": str(latest), "mtime": latest.stat().st_mtime, "csv_text": text}


def list_uploaded_logs(upload_dir: Path) -> list[Path]:
    if not upload_dir.exists() or not upload_dir.is_dir():
        return []
    return sorted([p for p in upload_dir.iterdir() if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)


def read_uploaded_log(path: Path, *, max_bytes: int = 400_000) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raw = raw[-max_bytes:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")
    return {"path": str(path), "mtime": path.stat().st_mtime, "csv_text": text}

