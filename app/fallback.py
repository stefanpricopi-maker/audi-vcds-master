from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class Fault:
    module: str
    code: str
    text: str
    status: str | None = None


def _looks_like_fault_line(line: str) -> bool:
    # Very loose heuristics for our synthetic CSV and common scan dumps.
    l = line.lower()
    return (
        "p0" in l
        or "p1" in l
        or "p2" in l
        or "p3" in l
        or "abs" in l
        or "engine" in l
        or "address" in l
    )


def extract_faults(text: str) -> list[Fault]:
    faults: list[Fault] = []
    current_module: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue

        # VCDS Auto-Scan often has: "Address 01: Engine"
        m_addr = re.match(r"^Address\s+(\S+):\s*(.+)$", line)
        if m_addr:
            current_module = f"{m_addr.group(1)}-{m_addr.group(2).strip()}"
            continue

        # Synthetic CSV: Address,Subsystem,FaultCode,FaultText,Status,...
        if "," in line and not line.lower().startswith("address,"):
            parts = [p.strip().strip('"') for p in line.split(",")]
            if len(parts) >= 5 and parts[2].upper().startswith(("P0", "P1", "P2", "P3")):
                faults.append(
                    Fault(
                        module=parts[0] or "unknown",
                        code=parts[2],
                        text=parts[3] or "",
                        status=parts[4] or None,
                    )
                )
                continue
            # ABS/etc often use numeric codes (e.g., 00290)
            if len(parts) >= 5 and parts[2] and parts[2].isdigit():
                faults.append(
                    Fault(
                        module=parts[0] or "unknown",
                        code=parts[2],
                        text=parts[3] or "",
                        status=parts[4] or None,
                    )
                )
                continue

        # VCDS DTC line pattern example:
        # "16683 - Boost Pressure Regulation: Control Range Not Reached"
        # followed by "P0299 - 000 - Control Range Not Reached - Intermittent"
        m_vcds = re.match(r"^(\d{3,6})\s*-\s*(.+)$", line)
        if m_vcds and _looks_like_fault_line(line):
            faults.append(
                Fault(
                    module=current_module or "unknown",
                    code=m_vcds.group(1),
                    text=m_vcds.group(2).strip(),
                )
            )
            continue

        m_pcode = re.match(
            r"^(P\d{4})\s*-\s*\d+\s*-\s*(.+?)(?:\s*-\s*(Intermittent|Static).*)?$",
            line,
            flags=re.IGNORECASE,
        )
        if m_pcode:
            faults.append(
                Fault(
                    module=current_module or "unknown",
                    code=m_pcode.group(1).upper(),
                    text=m_pcode.group(2).strip(),
                    status=m_pcode.group(3),
                )
            )
            continue

        # Generic: "P0299 - ...", "00290 - ..."
        if "-" in line and _looks_like_fault_line(line):
            left, right = line.split("-", 1)
            code = left.strip()
            desc = right.strip()
            if code:
                faults.append(Fault(module=current_module or "unknown", code=code, text=desc))

    # Dedupe (module+code)
    seen: set[tuple[str, str]] = set()
    out: list[Fault] = []
    for f in faults:
        key = (f.module, f.code)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def _steps_for_fault(code: str, text: str) -> list[str]:
    c = code.upper()
    t = text.lower()

    if c == "P0299" or "underboost" in t:
        return [
            "Verifică furtunele de vacuum (fisuri, coliere, îmbinări), în special spre N75 și actuatorul turbinei.",
            "Verifică N75: conector, rezistență bobină (comparativ cu specificația), furtune conectate corect.",
            "Verifică actuatorul turbinei/VNT: cursă liberă, gripare, vacuum hold (pompiță vacuum).",
            "Verifică scăpări pe traseul de presiune: intercooler, furtune, coliere, eventual fisuri.",
            "Log recomandat: boost specified vs actual + N75 duty + MAF în accelerație (treapta 3/4, 1500→3500 rpm).",
        ]

    if c == "P0101" or "maf" in t:
        return [
            "Verifică filtrul de aer și traseul de admisie pentru fals aer după MAF.",
            "Curăță/verifică conectorul MAF; inspectează cablajul (fire rupte/oxidare).",
            "Compară MAF actual vs expected în log (idle + accelerație).",
            "Dacă ai și P0299, tratează întâi sub-boost (poate distorsiona MAF).",
        ]

    if "00290" in c or ("abs" in t and "wheel speed" in t):
        return [
            "Verifică senzorul ABS pe roata indicată: mufă, cablaj, mizerie la senzor/inel.",
            "Verifică continuitatea cablajului până la modulul ABS (mai ales dacă eroarea e intermitentă).",
            "Dacă eroarea apare la 0 km/h, verifică alimentări/masă și starea bateriei.",
        ]

    return [
        "Spune-mi tipul exact de scan (Auto-Scan vs measuring blocks) și copia integrală a liniilor de fault pentru acest cod.",
        "Confirmă simptomele (martori în bord, când apare, condiții).",
    ]


_URL_RE = re.compile(r"https?://[^\s)]+")


def _extract_urls(s: str) -> list[str]:
    urls = _URL_RE.findall(s or "")
    # Notes often wrap URLs in backticks; strip common trailing punctuation.
    cleaned: list[str] = []
    for u in urls:
        u2 = u.rstrip("`'\".,;:)]}>")
        cleaned.append(u2)
    return cleaned


def _build_references(chunks: list[dict[str, Any]], *, max_sources: int = 4) -> list[str]:
    """
    Build reference bullets from retrieved chunks.
    We prefer URLs present in the chunk text. Otherwise, we cite the source filename.
    """
    refs: list[str] = []
    seen: set[str] = set()

    for ch in chunks:
        md = ch.get("metadata", {}) or {}
        source = md.get("source") or "unknown_source"
        text = ch.get("text") or ""
        urls = _extract_urls(text)

        if urls:
            for u in urls[:2]:
                key = f"{source}|{u}"
                if key in seen:
                    continue
                seen.add(key)
                refs.append(f"- {source}: {u}")
                if len(refs) >= max_sources:
                    return refs
        else:
            key = source
            if key in seen:
                continue
            seen.add(key)
            refs.append(f"- {source}")
            if len(refs) >= max_sources:
                return refs

    return refs


def steps_for_fault(code: str, text: str) -> list[str]:
    return _steps_for_fault(code, text)


def build_references(chunks: list[dict[str, Any]], *, max_sources: int = 4) -> list[str]:
    return _build_references(chunks, max_sources=max_sources)


def generate_fallback_answer(
    message: str,
    *,
    vcds_csv_text: str | None,
    retrieved_chunks: list[dict[str, Any]] | None = None,
) -> str:
    lines: list[str] = []
    lines.append("**Ce am observat**")

    faults: list[Fault] = extract_faults(vcds_csv_text or "") if vcds_csv_text else []
    if faults:
        for f in faults:
            st = f" ({f.status})" if f.status else ""
            lines.append(f"- {f.module}: {f.code} — {f.text}{st}")
    else:
        lines.append("- Nu am putut extrage coduri din log (sau nu ai inclus un log).")

    lines.append("")
    lines.append("**Ipoteze (ordonate)**")
    if any(f.code.upper() == "P0299" or "underboost" in f.text.lower() for f in faults):
        lines.append("- Pierdere vacuum / comandă VNT (N75, furtune, actuator).")
        lines.append("- Scăpare pe traseul de presiune (intercooler/furtune).")
        lines.append("- Eroare de măsură (MAF) sau EGR care afectează încărcarea.")
    else:
        lines.append("- Am nevoie de mai mult context (simptome + coduri complete).")

    lines.append("")
    lines.append("**Pași de verificare (ordine)**")

    # Prioritize P0299 then other faults
    ordered = sorted(faults, key=lambda f: 0 if f.code.upper() == "P0299" else 1)
    steps: list[str] = []
    for f in ordered[:3]:
        steps.extend(_steps_for_fault(f.code, f.text))

    if not steps:
        steps = [
            "Încarcă un log VCDS (Auto-Scan sau log de measuring blocks) și bifează `include_latest_uploaded_log`.",
            "Spune ce simptome ai (lipsă putere, limp mode, fum, când apare).",
        ]

    # De-dupe steps preserving order
    seen_steps: set[str] = set()
    deduped: list[str] = []
    for s in steps:
        if s in seen_steps:
            continue
        seen_steps.add(s)
        deduped.append(s)

    for i, s in enumerate(deduped[:10], start=1):
        lines.append(f"{i}. {s}")

    lines.append("")
    lines.append("**Referințe**")
    refs = _build_references(retrieved_chunks or [])
    if refs:
        lines.extend(refs)
        lines.append(
            "- Notă: surse din indexul tău local (note în `knowledge/public`, PDF-uri ingestate; nu înlocuiesc manuale OEM/Bentley dacă nu le-ai indexat)."
        )
    else:
        lines.append(
            "- (Fallback mode) Nu am găsit referințe relevante în indexul local. Rulează `/search` sau adaugă note/manuale."
        )

    return "\n".join(lines)

