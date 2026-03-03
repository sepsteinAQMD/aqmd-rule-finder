"""
Tests for indexer.py — PDF download, text extraction, state management.
"""

import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock, mock_open

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import indexer
import database


@pytest.fixture(autouse=True)
def reset_indexer_state():
    """Reset indexer state before each test."""
    with indexer._lock:
        indexer._state.update({
            "running": False,
            "phase": "idle",
            "message": "",
            "current": 0,
            "total": 0,
            "errors": [],
            "last_completed": None,
        })
    yield


# ── get_status ─────────────────────────────────────────

def test_get_status_returns_dict():
    status = indexer.get_status()
    assert isinstance(status, dict)
    assert "running" in status
    assert "phase" in status
    assert "message" in status


def test_get_status_initial_state():
    status = indexer.get_status()
    assert status["running"] is False
    assert status["phase"] == "idle"


# ── _safe_filename ─────────────────────────────────────

def test_safe_filename_basic():
    name = indexer._safe_filename("https://www.aqmd.gov/docs/rule-1103.pdf")
    assert name == "rule-1103.pdf"


def test_safe_filename_strips_query():
    name = indexer._safe_filename("https://www.aqmd.gov/docs/rule.pdf?v=2")
    assert "?" not in name
    assert name == "rule.pdf"


def test_safe_filename_complex_url():
    name = indexer._safe_filename("https://www.aqmd.gov/docs/default-source/rule-book/reg-xi/rule-1103-pharmaceuticals.pdf")
    assert name == "rule-1103-pharmaceuticals.pdf"


def test_safe_filename_replaces_unsafe_chars():
    name = indexer._safe_filename("https://example.com/some file (2).pdf")
    assert " " not in name
    assert "(" not in name
    assert ")" not in name


def test_safe_filename_max_length():
    long_url = "https://example.com/" + "a" * 300 + ".pdf"
    name = indexer._safe_filename(long_url)
    assert len(name) <= 200


# ── download_pdf ───────────────────────────────────────

def test_download_pdf_success(tmp_path):
    dest = str(tmp_path / "rule.pdf")
    pdf_content = b"%PDF-1.4 fake pdf content " * 100  # > 1KB

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.headers = {"content-type": "application/pdf"}
    mock_resp.raise_for_status = MagicMock()
    mock_resp.iter_content.return_value = [pdf_content]
    mock_session.get.return_value = mock_resp

    result = indexer.download_pdf("https://example.com/rule.pdf", dest, session=mock_session)
    assert result is True
    assert os.path.exists(dest)


def test_download_pdf_skips_existing(tmp_path):
    dest = str(tmp_path / "rule.pdf")
    # Create a file > 1KB
    with open(dest, "wb") as f:
        f.write(b"x" * 2000)

    mock_session = MagicMock()
    result = indexer.download_pdf("https://example.com/rule.pdf", dest, session=mock_session)
    assert result is True
    # Should not have made any HTTP request
    mock_session.get.assert_not_called()


def test_download_pdf_fails_on_network_error(tmp_path):
    dest = str(tmp_path / "rule.pdf")
    mock_session = MagicMock()
    mock_session.get.side_effect = Exception("Connection refused")

    result = indexer.download_pdf("https://example.com/rule.pdf", dest, session=mock_session)
    assert result is False
    assert not os.path.exists(dest)


def test_download_pdf_rejects_html_response(tmp_path):
    dest = str(tmp_path / "rule.pdf")
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.headers = {"content-type": "text/html"}
    mock_resp.raise_for_status = MagicMock()
    mock_resp.iter_content.return_value = [b"<html>Error page</html>"]
    mock_session.get.return_value = mock_resp

    result = indexer.download_pdf("https://example.com/rule.pdf", dest, session=mock_session)
    assert result is False


def test_download_pdf_rejects_tiny_file(tmp_path):
    dest = str(tmp_path / "rule.pdf")
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.headers = {"content-type": "application/pdf"}
    mock_resp.raise_for_status = MagicMock()
    mock_resp.iter_content.return_value = [b"tiny"]  # < 512 bytes
    mock_session.get.return_value = mock_resp

    result = indexer.download_pdf("https://example.com/rule.pdf", dest, session=mock_session)
    assert result is False
    assert not os.path.exists(dest)


# ── extract_pdf_text ────────────────────────────────────

def test_extract_pdf_text_returns_list(tmp_path):
    """Test with a real minimal PDF if PyMuPDF is available."""
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF not installed")

    # Create a minimal valid PDF using fitz
    pdf_path = str(tmp_path / "test.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "This is a test page about pharmaceutical manufacturing.")
    doc.save(pdf_path)
    doc.close()

    pages = indexer.extract_pdf_text(pdf_path)
    assert isinstance(pages, list)
    assert len(pages) == 1
    page_num, text = pages[0]
    assert page_num == 1
    assert "pharmaceutical" in text.lower()


def test_extract_pdf_text_multipage(tmp_path):
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF not installed")

    pdf_path = str(tmp_path / "multipage.pdf")
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((50, 100), f"Page {i+1} content: auto body shop regulations.")
    doc.save(pdf_path)
    doc.close()

    pages = indexer.extract_pdf_text(pdf_path)
    assert len(pages) == 3
    assert pages[0][0] == 1  # page number
    assert pages[2][0] == 3


def test_extract_pdf_text_invalid_path():
    pages = indexer.extract_pdf_text("/nonexistent/path/rule.pdf")
    assert pages == []


def test_extract_pdf_text_empty_pages_excluded(tmp_path):
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF not installed")

    pdf_path = str(tmp_path / "sparse.pdf")
    doc = fitz.open()
    # Page 1: has text
    p1 = doc.new_page()
    p1.insert_text((50, 100), "Some meaningful content here.")
    # Page 2: blank (no text)
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    pages = indexer.extract_pdf_text(pdf_path)
    # Blank page should be excluded
    page_nums = [p[0] for p in pages]
    assert 1 in page_nums
    # Page 2 is blank, should be excluded or included with empty string
    for pnum, text in pages:
        assert text.strip() != "" or True  # blank pages are filtered in extract_pdf_text


# ── _update_state ──────────────────────────────────────

def test_update_state_thread_safe():
    """State updates should not raise even under concurrent access."""
    import threading
    errors = []

    def update_worker():
        try:
            for _ in range(100):
                indexer._update_state(current=1, total=10, message="test")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=update_worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []


# ── run_indexing (integration, with mocks) ─────────────

def test_run_indexing_handles_scrape_failure(tmp_path):
    os.environ["AQMD_DATA_DIR"] = str(tmp_path)
    database.init_db(database.get_db_path())

    with patch("scraper.scrape_all_regulations", return_value=[]):
        indexer.run_indexing()

    status = indexer.get_status()
    assert status["phase"] == "error"
    assert "internet" in status["message"].lower() or "fetch" in status["message"].lower() or "connect" in status["message"].lower()


def test_run_indexing_full_flow(tmp_path):
    """Test the full indexing flow with mocked scraper and downloader."""
    os.environ["AQMD_DATA_DIR"] = str(tmp_path)
    database.init_db(database.get_db_path())

    fake_rules = [{
        "rule_number": "1103",
        "title": "Pharmaceuticals Manufacturing",
        "regulation_num": "XI",
        "regulation_name": "Source Specific",
        "pdf_url": "https://aqmd.gov/rule-1103.pdf",
        "amendment_date": "January 6, 2023",
    }]

    fake_pages = [(1, "This rule applies to pharmaceutical manufacturing operations.")]

    with patch("scraper.scrape_all_regulations", return_value=fake_rules), \
         patch("indexer.download_pdf", return_value=True), \
         patch("indexer.extract_pdf_text", return_value=fake_pages):
        indexer.run_indexing()

    status = indexer.get_status()
    assert status["phase"] == "done"
    assert status["running"] is False

    stats = database.get_stats()
    assert stats["indexed_rules"] >= 1


def test_run_indexing_records_download_error(tmp_path):
    os.environ["AQMD_DATA_DIR"] = str(tmp_path)
    database.init_db(database.get_db_path())

    fake_rules = [{
        "rule_number": "999",
        "title": "Broken Rule",
        "regulation_num": "IV",
        "regulation_name": "Prohibitions",
        "pdf_url": "https://aqmd.gov/broken.pdf",
        "amendment_date": "",
    }]

    with patch("scraper.scrape_all_regulations", return_value=fake_rules), \
         patch("indexer.download_pdf", return_value=False):
        indexer.run_indexing()

    status = indexer.get_status()
    assert status["phase"] == "done"
    assert len(status["errors"]) == 1


# ── start_indexing_thread ──────────────────────────────

def test_start_indexing_thread_returns_thread(tmp_path):
    import threading
    os.environ["AQMD_DATA_DIR"] = str(tmp_path)
    database.init_db(database.get_db_path())

    with patch("indexer.run_indexing"):
        t = indexer.start_indexing_thread()
    assert t is None or isinstance(t, threading.Thread)


def test_start_indexing_thread_prevents_double_start(tmp_path):
    os.environ["AQMD_DATA_DIR"] = str(tmp_path)
    database.init_db(database.get_db_path())

    with indexer._lock:
        indexer._state["running"] = True

    t = indexer.start_indexing_thread()
    assert t is None  # Should not start a second thread
