from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

_FIXTURE_CSV = Path(__file__).resolve().parents[1] / "fixtures" / "uploaded_snapshot_minimal.csv"


def test_upload_fixture_then_list_logs(page: Page, base_url: str) -> None:
    page.goto(base_url + "/")
    _upload_and_refresh_logs(page)
    expect(page.locator("#pickedPath option")).not_to_have_count(0, timeout=15_000)


def _upload_and_refresh_logs(page: Page) -> None:
    page.locator("#uploadLogDetails").evaluate("(d) => { d.open = true; }")
    page.set_input_files("#fileInput", str(_FIXTURE_CSV))
    page.locator("#btnUpload").click()
    expect(page.locator("#outStatus")).to_contain_text("Upload OK", timeout=30_000)
    page.locator("#actionsDetails").evaluate("(d) => { d.open = true; }")
    page.locator("#btnLogs").click()
    expect(page.locator("#outStatus")).to_contain_text("OK", timeout=30_000)


def test_compare_reports_two_uploads(page: Page, base_url: str) -> None:
    page.goto(base_url + "/")
    _upload_and_refresh_logs(page)
    _upload_and_refresh_logs(page)
    opts = page.locator("#pickedPath option")
    expect(opts).not_to_have_count(0, timeout=15_000)
    assert opts.count() >= 2, "need at least two uploaded logs for compare"
    page.locator("#pickedPath").select_option(index=0)
    page.locator("#pickedPathB").select_option(index=1)
    page.locator("#btnCompareReports").click()
    expect(page.locator("#outStatus")).to_contain_text("Comparație rapoarte gata", timeout=30_000)
    expect(page.locator("#outputMd")).to_contain_text("Comparație — două rapoarte Markdown", timeout=15_000)
    expect(page.locator("#outputMd")).to_contain_text("P0299")


def test_chat_fallback_via_api(page: Page, base_url: str) -> None:
    page.goto(base_url + "/")
    resp = page.request.post(
        f"{base_url}/chat",
        data=json.dumps(
            {
                "message": "Răspuns foarte scurt: ce înseamnă P0299 la o mașină diesel?",
                "include_latest_vcds_log": False,
                "include_latest_uploaded_log": False,
            }
        ),
        headers={"Content-Type": "application/json"},
    )
    assert resp.ok
    body = resp.json()
    assert isinstance(body.get("answer"), str)
    assert len(body["answer"]) > 20
