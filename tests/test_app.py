"""
Tests for app.py — Flask routes and API endpoints.
"""

import os
import sys
import json
import pytest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment before importing app
os.environ["AQMD_NO_BROWSER"] = "1"

import database
import app as flask_app


@pytest.fixture
def tmp_data(tmp_path):
    os.environ["AQMD_DATA_DIR"] = str(tmp_path)
    database.init_db()
    return tmp_path


@pytest.fixture
def client(tmp_data):
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c


# ── GET / ──────────────────────────────────────────────

def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"AQMD Rule Finder" in resp.data


def test_index_content_type(client):
    resp = client.get("/")
    assert "text/html" in resp.content_type


# ── GET /api/status ────────────────────────────────────

def test_api_status_returns_json(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "total_rules" in data
    assert "indexed_rules" in data
    assert "phase" in data


def test_api_status_initial_values(client):
    resp = client.get("/api/status")
    data = json.loads(resp.data)
    assert data["total_rules"] == 0
    assert data["indexed_rules"] == 0


# ── GET /api/search ────────────────────────────────────

def test_api_search_empty_query(client):
    resp = client.get("/api/search?q=")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["results"] == []
    assert data["total"] == 0


def test_api_search_missing_query(client):
    resp = client.get("/api/search")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["results"] == []


def test_api_search_no_results(client):
    resp = client.get("/api/search?q=xyznotfound12345")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["results"] == []
    assert data["total"] == 0


def test_api_search_with_indexed_data(client, tmp_data):
    # Insert test data
    with database.get_connection() as conn:
        rule_id = database.upsert_rule(
            conn, "1103", "Pharmaceuticals Manufacturing", "XI", "Source Specific",
            "https://aqmd.gov/rule-1103.pdf", "2023"
        )
        database.insert_page(conn, rule_id, 1, "pharmaceutical manufacturing operations and equipment.")
        database.mark_rule_indexed(conn, rule_id)

    resp = client.get("/api/search?q=pharmaceutical")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["total"] > 0
    assert len(data["results"]) > 0
    assert data["results"][0]["rule_number"] == "1103"


def test_api_search_returns_matches(client, tmp_data):
    with database.get_connection() as conn:
        rule_id = database.upsert_rule(
            conn, "401", "Visible Emissions", "IV", "Prohibitions",
            "https://aqmd.gov/rule-401.pdf", "2001"
        )
        database.insert_page(conn, rule_id, 3, "No person shall discharge visible emissions from any source.")
        database.mark_rule_indexed(conn, rule_id)

    resp = client.get("/api/search?q=visible+emissions")
    data = json.loads(resp.data)
    assert len(data["results"]) > 0
    result = data["results"][0]
    assert "matches" in result
    assert len(result["matches"]) > 0
    match = result["matches"][0]
    assert "page" in match
    assert "excerpt" in match


def test_api_search_limit_param(client, tmp_data):
    with database.get_connection() as conn:
        for i in range(5):
            rid = database.upsert_rule(
                conn, str(400 + i), f"Rule {400+i}", "IV", "Prohibitions",
                f"https://aqmd.gov/rule-{400+i}.pdf", "2023"
            )
            database.insert_page(conn, rid, 1, f"emissions from industrial operations rule {400+i}.")
            database.mark_rule_indexed(conn, rid)

    resp = client.get("/api/search?q=emissions&limit=2")
    data = json.loads(resp.data)
    assert len(data["results"]) <= 2


def test_api_search_invalid_limit_handled(client):
    resp = client.get("/api/search?q=test&limit=abc")
    assert resp.status_code == 200


def test_api_search_special_chars(client):
    for query in ["(test)", '"quoted"', "AND OR NOT", "a*", "test:"]:
        resp = client.get(f"/api/search?q={query}")
        assert resp.status_code == 200


# ── GET /api/rules ─────────────────────────────────────

def test_api_rules_empty(client):
    resp = client.get("/api/rules")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["rules"] == []
    assert data["total"] == 0


def test_api_rules_with_data(client, tmp_data):
    with database.get_connection() as conn:
        database.upsert_rule(conn, "401", "Visible Emissions", "IV", "Prohibitions",
                             "https://aqmd.gov/rule-401.pdf", "2001")
        database.upsert_rule(conn, "403", "Fugitive Dust", "IV", "Prohibitions",
                             "https://aqmd.gov/rule-403.pdf", "2005")

    resp = client.get("/api/rules")
    data = json.loads(resp.data)
    assert data["total"] == 2
    assert len(data["rules"]) == 2


def test_api_rules_filter_by_regulation(client, tmp_data):
    with database.get_connection() as conn:
        database.upsert_rule(conn, "401", "Visible Emissions", "IV", "Prohibitions",
                             "https://aqmd.gov/rule-401.pdf", "2001")
        database.upsert_rule(conn, "1103", "Pharmaceuticals", "XI", "Source Specific",
                             "https://aqmd.gov/rule-1103.pdf", "2023")

    resp = client.get("/api/rules?regulation=IV")
    data = json.loads(resp.data)
    assert data["total"] == 1
    assert data["rules"][0]["rule_number"] == "401"


def test_api_rules_pagination(client, tmp_data):
    with database.get_connection() as conn:
        for i in range(5):
            database.upsert_rule(
                conn, str(400 + i), f"Rule {400+i}", "IV", "Prohibitions",
                f"https://aqmd.gov/rule-{400+i}.pdf", "2023"
            )

    resp = client.get("/api/rules?limit=2&offset=0")
    data = json.loads(resp.data)
    assert len(data["rules"]) == 2

    resp2 = client.get("/api/rules?limit=2&offset=2")
    data2 = json.loads(resp2.data)
    assert len(data2["rules"]) == 2
    # Ensure different rules
    ids1 = {r["rule_number"] for r in data["rules"]}
    ids2 = {r["rule_number"] for r in data2["rules"]}
    assert ids1.isdisjoint(ids2)


# ── POST /api/refresh ──────────────────────────────────

def test_api_refresh_starts_indexing(client):
    from unittest.mock import patch
    with patch("indexer.start_indexing_thread") as mock_start:
        resp = client.post("/api/refresh")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "started" in data


def test_api_refresh_does_not_double_start(client):
    from unittest.mock import patch
    import indexer
    with indexer._lock:
        indexer._state["running"] = True
    try:
        resp = client.post("/api/refresh")
        data = json.loads(resp.data)
        assert data["started"] is False
    finally:
        with indexer._lock:
            indexer._state["running"] = False


# ── GET /pdf/<filename> ────────────────────────────────

def test_api_pdf_not_found(client):
    resp = client.get("/pdf/nonexistent.pdf")
    assert resp.status_code == 404


def test_api_pdf_path_traversal_blocked(client, tmp_data):
    # Attempt path traversal
    resp = client.get("/pdf/../../../etc/passwd")
    assert resp.status_code in (400, 403, 404)


def test_api_pdf_serves_existing_file(client, tmp_data):
    # Create a fake PDF in the pdf dir
    pdf_dir = database.get_pdf_dir()
    pdf_path = os.path.join(pdf_dir, "test.pdf")
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 test content " * 100)

    resp = client.get("/pdf/test.pdf")
    assert resp.status_code == 200
    assert resp.content_type == "application/pdf"


# ── SSE /api/progress/stream ───────────────────────────

def test_api_progress_stream_returns_sse(client):
    # Just check headers; don't consume the stream
    resp = client.get("/api/progress/stream", headers={"Accept": "text/event-stream"})
    # Flask test client may buffer, so we just check it doesn't 404/500
    assert resp.status_code == 200
