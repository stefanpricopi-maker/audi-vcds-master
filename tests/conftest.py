from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("E2E", "").strip().lower() in ("1", "true", "yes"):
        return
    skip_e2e = pytest.mark.skip(reason="Playwright e2e: set E2E=1 and install browsers (python -m playwright install chromium)")
    for item in items:
        if item.get_closest_marker("e2e"):
            item.add_marker(skip_e2e)
