from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MeasuringSummary:
    format: str
    row_count: int
    columns: list[str]
    signals_found: list[str]
    findings: list[str]
    stats: dict[str, Any]


def _to_float(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    # Handle comma decimal
    s = s.replace(",", ".")
    # Strip units
    s = re.sub(r"[^\d.\-]+", "", s)
    if not s or s in (".", "-", "-."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def looks_like_measuring_log(text: str) -> bool:
    head = "\n".join(text.splitlines()[:10]).lower()
    # Very rough heuristics: measuring logs often have many delimiters and a TIME/RPM header.
    return (
        ("time" in head or "zeit" in head)
        and ("rpm" in head or "engine speed" in head or "motordrehzahl" in head)
        and (head.count(";") >= 3 or head.count(",") >= 3 or "\t" in head)
    )


def parse_measuring_log(text: str, *, max_rows: int = 5000) -> MeasuringSummary | None:
    if not looks_like_measuring_log(text):
        return None

    # Detect delimiter by simple counts on first non-empty line
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith(";")]
    if len(lines) < 2:
        return None

    sample = lines[0]
    delim = ";"
    if sample.count("\t") > sample.count(";") and sample.count("\t") > sample.count(","):
        delim = "\t"
    elif sample.count(",") > sample.count(";"):
        delim = ","

    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delim)
    try:
        header = next(reader)
    except StopIteration:
        return None

    cols = [c.strip() for c in header if c is not None]
    cols_l = [c.lower() for c in cols]

    def find_col(keys: list[str]) -> int | None:
        for i, c in enumerate(cols_l):
            for k in keys:
                if k in c:
                    return i
        return None

    idx_rpm = find_col(["rpm", "engine speed", "motordrehzahl"])
    idx_boost_spec = find_col(["specified", "target", "sol", "desired", "req", "soll", "spec"])
    idx_boost_act = find_col(["actual", "ist", "measured"])
    # Try boost specific naming
    idx_boost = find_col(["boost", "charge pressure", "ladedruck"])
    idx_n75 = find_col(["n75", "duty", "takt", "regelventil"])
    idx_maf = find_col(["maf", "mg/str", "luftmasse", "air mass"])

    # If "boost" exists but specified/actual not found, we can't do much.
    # Common exports have columns like "Boost Pressure (specified)" and "(actual)".
    # Heuristic: if we found idx_boost, search for two boost columns.
    if idx_boost is not None and (idx_boost_spec is None or idx_boost_act is None):
        boost_cols = [i for i, c in enumerate(cols_l) if ("boost" in c or "charge pressure" in c or "ladedruck" in c)]
        if len(boost_cols) >= 2:
            # choose by keywords
            for i in boost_cols:
                c = cols_l[i]
                if idx_boost_spec is None and any(k in c for k in ["specified", "soll", "target", "desired", "req"]):
                    idx_boost_spec = i
                if idx_boost_act is None and any(k in c for k in ["actual", "ist", "measured"]):
                    idx_boost_act = i

    rpm: list[float] = []
    boost_spec: list[float] = []
    boost_act: list[float] = []
    n75: list[float] = []
    maf: list[float] = []

    row_count = 0
    for row in reader:
        if not row:
            continue
        row_count += 1
        if row_count > max_rows:
            break

        def get(i: int | None) -> float | None:
            if i is None:
                return None
            if i >= len(row):
                return None
            return _to_float(row[i])

        v_rpm = get(idx_rpm)
        if v_rpm is not None:
            rpm.append(v_rpm)
        v_bs = get(idx_boost_spec)
        v_ba = get(idx_boost_act)
        if v_bs is not None:
            boost_spec.append(v_bs)
        if v_ba is not None:
            boost_act.append(v_ba)
        v_n = get(idx_n75)
        if v_n is not None:
            n75.append(v_n)
        v_m = get(idx_maf)
        if v_m is not None:
            maf.append(v_m)

    signals: list[str] = []
    if idx_rpm is not None:
        signals.append("rpm")
    if idx_boost_spec is not None:
        signals.append("boost_specified")
    if idx_boost_act is not None:
        signals.append("boost_actual")
    if idx_n75 is not None:
        signals.append("n75_duty")
    if idx_maf is not None:
        signals.append("maf")

    findings: list[str] = []
    stats: dict[str, Any] = {"delimiter": delim}

    def _median(xs: list[float]) -> float | None:
        if not xs:
            return None
        ys = sorted(xs)
        mid = len(ys) // 2
        return ys[mid] if len(ys) % 2 == 1 else (ys[mid - 1] + ys[mid]) / 2

    # Under/over-boost heuristic if we have both
    if boost_spec and boost_act:
        min_len = min(len(boost_spec), len(boost_act))
        deltas = [boost_spec[i] - boost_act[i] for i in range(min_len)]
        md = _median(deltas)
        stats["boost_delta_median"] = md

        # Filter high-request segments
        hi = [deltas[i] for i in range(min_len) if boost_spec[i] >= 1800]
        md_hi = _median(hi)
        stats["boost_delta_median_hi_request"] = md_hi

        if md_hi is not None and md_hi > 200:
            if n75:
                md_n75 = _median(n75)
                stats["n75_median"] = md_n75
                if md_n75 is not None and md_n75 >= 70:
                    findings.append("Pattern consistent with underboost (actual boost significantly below specified) with high N75 duty → suspect vacuum/VNT control or boost leak.")
                else:
                    findings.append("Underboost pattern detected (actual below specified). N75 duty not high/unknown → consider sensor/log quality or other causes.")
            else:
                findings.append("Underboost pattern detected (actual boost below specified). Add N75 duty to logs for better diagnosis.")
        elif md_hi is not None and md_hi < -200:
            findings.append("Pattern consistent with overboost (actual boost above specified).")
        else:
            findings.append("No strong under/over-boost pattern detected from boost specified vs actual (heuristic).")
    else:
        findings.append("Boost specified/actual columns not found together; cannot evaluate under/over-boost pattern.")

    if maf:
        stats["maf_median"] = _median(maf)

    return MeasuringSummary(
        format="vcds_measuring",
        row_count=row_count,
        columns=cols,
        signals_found=signals,
        findings=findings,
        stats=stats,
    )


def summary_to_dict(s: MeasuringSummary) -> dict[str, Any]:
    return {
        "format": s.format,
        "row_count": s.row_count,
        "columns": s.columns[:60],
        "signals_found": s.signals_found,
        "findings": s.findings,
        "stats": s.stats,
    }

