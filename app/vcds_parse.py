from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedDtc:
    module: str
    vcds_code: str | None
    pcode: str | None
    text: str
    status: str | None = None
    freeze_frame: dict[str, str] | None = None


_RE_ADDR = re.compile(r"^Address\s+(\S+):\s*(.+)$")
_RE_VCDS_DTC = re.compile(r"^(\d{3,6})\s*-\s*(.+)$")
_RE_PCODE = re.compile(
    r"^(P\d{4})\s*-\s*\d+\s*-\s*(.+?)(?:\s*-\s*(Intermittent|Static).*)?$",
    flags=re.IGNORECASE,
)


def parse_vcds_text(text: str) -> list[ParsedDtc]:
    """
    Best-effort parser for VCDS Auto-Scan text output.
    Extracts module, DTC(s), P-code line (when present) and Freeze Frame key/values.
    """
    module: str | None = None
    out: list[ParsedDtc] = []

    current_vcds_code: str | None = None
    current_text: str | None = None
    current_pcode: str | None = None
    current_status: str | None = None
    in_freeze = False
    freeze: dict[str, str] = {}

    def flush():
        nonlocal current_vcds_code, current_text, current_pcode, current_status, in_freeze, freeze
        if module and (current_vcds_code or current_pcode) and current_text:
            out.append(
                ParsedDtc(
                    module=module,
                    vcds_code=current_vcds_code,
                    pcode=current_pcode,
                    text=current_text.strip(),
                    status=current_status,
                    freeze_frame=freeze or None,
                )
            )
        current_vcds_code = None
        current_text = None
        current_pcode = None
        current_status = None
        in_freeze = False
        freeze = {}

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            if in_freeze and not line:
                in_freeze = False
            continue

        m_addr = _RE_ADDR.match(line)
        if m_addr:
            flush()
            module = f"{m_addr.group(1)}-{m_addr.group(2).strip()}"
            continue

        if line.lower().startswith("freeze frame"):
            in_freeze = True
            continue

        if in_freeze:
            # Typical "RPM: 2780 /min"
            if ":" in line:
                k, v = line.split(":", 1)
                freeze[k.strip()] = v.strip()
            continue

        m_vcds = _RE_VCDS_DTC.match(line)
        if m_vcds and module:
            # Starting a new DTC; flush previous.
            if current_vcds_code or current_pcode:
                flush()
            current_vcds_code = m_vcds.group(1)
            current_text = m_vcds.group(2)
            continue

        m_p = _RE_PCODE.match(line)
        if m_p and module:
            current_pcode = m_p.group(1).upper()
            # Prefer the P-code text if it's more specific than the numeric line.
            if current_text is None:
                current_text = m_p.group(2)
            current_status = m_p.group(3)
            continue

    flush()
    return out


def parsed_to_fault_dicts(parsed: list[ParsedDtc]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in parsed:
        out.append(
            {
                "module": p.module,
                "code": p.pcode or p.vcds_code or "unknown",
                "pcode": p.pcode,
                "vcds_code": p.vcds_code,
                "text": p.text,
                "status": p.status,
                "freeze_frame": p.freeze_frame,
            }
        )
    return out

