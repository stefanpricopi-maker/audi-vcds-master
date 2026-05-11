from __future__ import annotations

from pathlib import Path

import pytest

_STATIC = Path(__file__).resolve().parents[1] / "static" / "index.html"


@pytest.fixture
def index_html() -> str:
    assert _STATIC.is_file(), f"missing {_STATIC}"
    return _STATIC.read_text(encoding="utf-8")


def test_static_index_has_workshop_controls(index_html: str) -> None:
    """UI smoke: critical ids and workshop features remain wired in static/index.html."""
    for needle in (
        'id="btnWorkshopQuickAnalyze"',
        'id="pickedPathB"',
        'id="btnCompareAnalyzes"',
        'id="btnCompareReports"',
        'id="chatSearchBlock"',
        'id="chatSearchRagOffHint"',
        'id="btnPrintReport"',
        'id="btnDownloadReportHtml"',
        'id="btnFillDtcPrompt"',
        'id="caseHistoryList"',
        'id="chkShowRagIndex"',
        'id="ragSectionWrap"',
    ):
        assert needle in index_html, f"missing {needle}"


def test_static_index_no_removed_mode_toggle(index_html: str) -> None:
    assert "btnModeDeveloper" not in index_html
    assert "btnModeAtelier" not in index_html
