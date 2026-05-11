from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import pytest
from starlette.testclient import TestClient

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_openapi_tags(client: TestClient) -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    names = {t["name"] for t in r.json().get("tags", [])}
    assert names >= {"meta", "chat", "knowledge", "logs"}


def test_docs_and_redoc(client: TestClient) -> None:
    r = client.get("/docs")
    assert r.status_code == 200
    body = r.text.lower()
    assert "swagger" in body or "openapi" in body

    r2 = client.get("/redoc")
    assert r2.status_code == 200
    assert "redoc" in r2.text.lower()


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert "version" in body
    rid = r.headers.get("x-request-id")
    assert rid and len(rid) >= 8


def test_request_id_header_passthrough(client: TestClient) -> None:
    custom = "trace-abc-123"
    r = client.get("/health", headers={"X-Request-ID": custom})
    assert r.status_code == 200
    assert r.headers.get("x-request-id") == custom


def test_status(client: TestClient) -> None:
    r = client.get("/status")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert "counts" in data and "rag_chunks" in data["counts"]
    assert "paths" in data


def test_uploaded_context(client: TestClient) -> None:
    r = client.get("/uploaded-context", params={"recent_limit": 5, "max_bytes": 50_000})
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert "recent_files" in data
    assert "base" in data
    if data["recent_files"]:
        assert data.get("log") is not None
        assert "csv_text" in data["log"]
    else:
        assert data.get("log") is None
        assert "read_error" in data


def test_uploaded_context_non_empty_with_fixture_tmpdir(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-API-003 (ramura cu fișier): recent_files + log.csv_text fără `data/uploaded-logs` populat."""
    import app.main as main

    log_path = tmp_path / "context_fixture.csv"
    shutil.copyfile(_FIXTURES / "uploaded_snapshot_minimal.csv", log_path)
    monkeypatch.setattr(main, "UPLOADED_LOGS_DIR", tmp_path)

    r = client.get("/uploaded-context", params={"recent_limit": 5, "max_bytes": 50_000})
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert len(data.get("recent_files") or []) >= 1
    log = data.get("log") or {}
    assert "csv_text" in log
    assert "P0299" in log["csv_text"]

    r2 = client.get(
        "/uploaded-context",
        params={"path": str(log_path.resolve()), "recent_limit": 5, "max_bytes": 50_000},
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2.get("ok") is True
    assert data2.get("selection") == "explicit"
    log2 = data2.get("log") or {}
    assert "P0299" in log2.get("csv_text", "")


def test_logs_uploaded(client: TestClient) -> None:
    r = client.get("/logs", params={"source": "uploaded", "limit": 10})
    assert r.status_code == 200
    data = r.json()
    assert data.get("source") == "uploaded"
    assert "items" in data
    for it in data["items"]:
        assert it.get("kind") in ("autoscan", "measuring", "unknown")


def test_analyze_latest_log_uploaded(client: TestClient) -> None:
    r = client.get("/analyze-latest-log", params={"source": "uploaded"})
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        data = r.json()
        assert "faults" in data
        assert "format" in data


def test_report_latest_log_uploaded(client: TestClient) -> None:
    r = client.get("/report-latest-log", params={"source": "uploaded"})
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        data = r.json()
        assert "report_markdown" in data
        assert len(data["report_markdown"]) > 20


def test_vcds_context_when_dir_unset(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main

    monkeypatch.setattr(main, "VCDS_LOG_DIR", None)
    r = client.get("/vcds-context")
    assert r.status_code == 200
    assert r.json().get("ok") is False


def test_logs_vcds_when_dir_unset(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main

    monkeypatch.setattr(main, "VCDS_LOG_DIR", None)
    r = client.get("/logs", params={"source": "vcds", "limit": 5})
    assert r.status_code == 400
    assert "VCDS_LOG_DIR" in r.json().get("detail", "")


def test_search_missing_query(client: TestClient) -> None:
    r = client.get("/search", params={"k": 5})
    assert r.status_code in (400, 422)

    r2 = client.get("/search", params={"q": "   ", "k": 5})
    assert r2.status_code == 400


def test_chat_fallback_without_log(client: TestClient) -> None:
    r = client.post(
        "/chat",
        json={
            "message": "Ce verifici primul dacă apare P0299 (underboost)?",
            "include_latest_vcds_log": False,
            "include_latest_uploaded_log": False,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("answer"), str) and len(data["answer"]) > 30
    assert isinstance(data.get("used_manual_chunks"), list)


def test_chat_emits_request_metadata_log(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="audi_vcds.chat"):
        r = client.post(
            "/chat",
            json={
                "message": "Scurt: ce e P0299?",
                "include_latest_vcds_log": False,
                "include_latest_uploaded_log": False,
            },
        )
    assert r.status_code == 200
    chat_logs = [rec.getMessage() for rec in caplog.records if rec.name == "audi_vcds.chat"]
    assert chat_logs, "expected audi_vcds.chat INFO line"
    payload = json.loads(chat_logs[0])
    assert payload["event"] == "chat_request"
    assert payload["include_latest_uploaded_log"] is False
    assert payload["message_chars"] >= 10
    assert "llm_mode" in payload


def test_chat_with_uploaded_snapshot(client: TestClient) -> None:
    r = client.post(
        "/chat",
        json={
            "message": "Rezumat extrem de scurt: ce fișiere recente vezi în snapshot?",
            "include_latest_vcds_log": False,
            "include_latest_uploaded_log": False,
            "include_uploaded_snapshot": True,
            "include_vcds_snapshot": False,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("answer"), str) and len(data["answer"]) > 10


def test_chat_vcds_snapshot_requires_dir(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main

    monkeypatch.setattr(main, "VCDS_LOG_DIR", None)
    r = client.post(
        "/chat",
        json={
            "message": "test",
            "include_vcds_snapshot": True,
            "include_latest_vcds_log": False,
            "include_latest_uploaded_log": False,
        },
    )
    assert r.status_code == 400


def test_chat_uploaded_snapshot_with_explicit_path(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-API-017: snapshot + path explicit, fără a depinde de `data/uploaded-logs` al mediului."""
    import app.main as main

    log_path = tmp_path / "pytest_uploaded_snapshot.csv"
    shutil.copyfile(_FIXTURES / "uploaded_snapshot_minimal.csv", log_path)
    monkeypatch.setattr(main, "UPLOADED_LOGS_DIR", tmp_path)

    r = client.post(
        "/chat",
        json={
            "message": "Ce cod de eroare apare în log?",
            "include_latest_vcds_log": False,
            "include_latest_uploaded_log": False,
            "include_uploaded_snapshot": True,
            "uploaded_snapshot_path": str(log_path.resolve()),
        },
    )
    assert r.status_code == 200
    answer = (r.json().get("answer") or "").lower()
    assert "p0299" in answer


def test_ingest_text_then_search(client: TestClient) -> None:
    token = "PYTEST-INGEST-TOKEN-xyz-789"
    r = client.post("/ingest-text", json={"source": "pytest", "title": "smoke", "text": f"Note: {token} for search."})
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"

    r2 = client.get("/search", params={"q": token, "k": 5})
    assert r2.status_code == 200
    texts = [x.get("text", "") for x in r2.json().get("results", [])]
    assert any(token in t for t in texts), json.dumps(r2.json(), indent=2)[:2000]
