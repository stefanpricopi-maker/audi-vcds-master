from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def _clear_ui_prefs(page: Page) -> None:
    page.evaluate("() => { localStorage.removeItem('audiVcdsShowRagIndex'); }")


def test_home_loads_title_and_workshop_strip(page: Page, base_url: str) -> None:
    page.goto(base_url + "/")
    expect(page).to_have_title(re.compile("Audi VCDS Master", re.I))
    expect(page.locator("h1")).to_contain_text("Audi VCDS Master")
    expect(page.locator("#workshopContext")).to_be_visible()


def test_workshop_strip_privacy_notice(page: Page, base_url: str) -> None:
    page.goto(base_url + "/")
    box = page.locator("#workshopContext")
    expect(box).to_contain_text("Nu trimite în câmpuri date personale")
    expect(box).to_contain_text("logurile sunt procesate pe acest server")


def test_static_controls_present(page: Page, base_url: str) -> None:
    page.goto(base_url + "/")
    for sid in (
        "btnWorkshopQuickAnalyze",
        "pickedPathB",
        "btnCompareAnalyzes",
        "btnCompareReports",
        "btnPrintReport",
        "btnDownloadReportHtml",
        "btnFillDtcPrompt",
        "caseHistoryList",
        "chkShowRagIndex",
        "ragSectionWrap",
    ):
        expect(page.locator(f"#{sid}")).to_be_attached()


def test_rag_section_hidden_until_checkbox(page: Page, base_url: str) -> None:
    page.goto(base_url + "/")
    _clear_ui_prefs(page)
    page.reload()
    wrap = page.locator("#ragSectionWrap")
    expect(wrap).to_be_hidden()
    page.locator("#chkShowRagIndex").check()
    expect(wrap).to_be_visible()
    page.locator("#chkShowRagIndex").uncheck()
    expect(wrap).to_be_hidden()


def test_rag_toggle_hides_chat_search_block(page: Page, base_url: str) -> None:
    page.goto(base_url + "/")
    _clear_ui_prefs(page)
    page.reload()
    page.locator("#chatSearchDetails").evaluate("(d) => { d.open = true; }")
    chat_block = page.locator("#chatSearchBlock")
    hint = page.locator("#chatSearchRagOffHint")
    expect(page.locator("#chkShowRagIndex")).not_to_be_checked()
    expect(chat_block).to_be_hidden()
    expect(hint).to_be_visible()
    page.locator("#chkShowRagIndex").check()
    expect(chat_block).to_be_visible()
    expect(hint).to_be_hidden()
