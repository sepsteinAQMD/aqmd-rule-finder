"""
Tests for scraper.py — rule number extraction and URL normalization.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scraper


# ── _normalize_pdf_url ─────────────────────────────────

def test_normalize_absolute_url():
    url = scraper._normalize_pdf_url("https://www.aqmd.gov/docs/rule-1103.pdf")
    assert url == "https://www.aqmd.gov/docs/rule-1103.pdf"


def test_normalize_relative_url():
    url = scraper._normalize_pdf_url("/docs/default-source/rule-book/reg-xi/rule-1103.pdf")
    assert url == "https://www.aqmd.gov/docs/default-source/rule-book/reg-xi/rule-1103.pdf"


def test_normalize_non_pdf_returns_none():
    assert scraper._normalize_pdf_url("/some/page.html") is None
    assert scraper._normalize_pdf_url("/some/image.jpg") is None


def test_normalize_none_returns_none():
    assert scraper._normalize_pdf_url(None) is None
    assert scraper._normalize_pdf_url("") is None


def test_normalize_protocol_relative():
    url = scraper._normalize_pdf_url("//www.aqmd.gov/docs/rule.pdf")
    assert url == "https://www.aqmd.gov/docs/rule.pdf"


def test_normalize_already_absolute():
    url = scraper._normalize_pdf_url("http://www.aqmd.gov/docs/rule.pdf")
    assert url == "http://www.aqmd.gov/docs/rule.pdf"


def test_normalize_url_with_query_string():
    """AQMD appends ?sfvrsn=... query strings to PDF URLs."""
    url = scraper._normalize_pdf_url("/docs/default-source/rule-book/rule-iv/rule-401.pdf?sfvrsn=e6df1d61_50")
    assert url is not None
    assert url.startswith("https://www.aqmd.gov")
    assert "rule-401.pdf" in url


def test_normalize_html_with_query_still_rejected():
    """A URL with .html before a query string should still be rejected."""
    assert scraper._normalize_pdf_url("/some/page.html?v=1") is None


# ── _extract_rule_number_from_text ─────────────────────

def test_extract_rule_number_standard():
    assert scraper._extract_rule_number_from_text("Rule 1103 Pharmaceuticals") == "1103"


def test_extract_rule_number_with_decimal():
    assert scraper._extract_rule_number_from_text("Rule 403.2 Fugitive Dust") == "403.2"


def test_extract_rule_number_with_letter():
    assert scraper._extract_rule_number_from_text("Rule 118.1 General Provision") == "118.1"


def test_extract_rule_number_no_match():
    assert scraper._extract_rule_number_from_text("No rule here") == ""


def test_extract_rule_number_case_insensitive():
    assert scraper._extract_rule_number_from_text("rule 401 visible emissions") == "401"


# ── _extract_rule_number_from_filename ─────────────────

def test_extract_from_filename_standard():
    assert scraper._extract_rule_number_from_filename("rule-1103-pharmaceuticals.pdf") == "1103"


def test_extract_from_filename_r_prefix():
    assert scraper._extract_rule_number_from_filename("r1113.pdf") == "1113"


def test_extract_from_filename_numeric():
    assert scraper._extract_rule_number_from_filename("rule-401.pdf") == "401"


def test_extract_from_filename_decimal():
    assert scraper._extract_rule_number_from_filename("rule-403-2.pdf") in ("403", "4032")


def test_extract_from_filename_no_match():
    # 'toc.pdf' - no rule number
    result = scraper._extract_rule_number_from_filename("toc.pdf")
    assert result == ""


# ── _extract_amendment_date ────────────────────────────

def test_extract_date_amended():
    text = "Rule 1103 (Amended January 6, 2023)"
    assert scraper._extract_amendment_date(text) == "January 6, 2023"


def test_extract_date_adopted():
    text = "Rule 401 (Adopted November 9, 2001)"
    assert scraper._extract_amendment_date(text) == "November 9, 2001"


def test_extract_date_none():
    assert scraper._extract_amendment_date("No date here") == ""


def test_extract_date_revised():
    text = "(Revised March 5, 2020)"
    assert scraper._extract_amendment_date(text) == "March 5, 2020"


# ── scrape_regulation_page (with mock) ─────────────────

MOCK_REG_XI_HTML = """
<html><body>
<table>
  <tr>
    <td><p><a href="/docs/default-source/rule-book/reg-xi/rule-1103-pharmaceuticals.pdf">Rule 1103</a> (PDF)</p></td>
    <td><p>Pharmaceuticals and Cosmetics Manufacturing<br>(Amended January 6, 2023)</p></td>
  </tr>
  <tr>
    <td><p><a href="/docs/default-source/rule-book/reg-xi/rule-1113-architectural.pdf">Rule 1113</a> (PDF)</p></td>
    <td><p>Architectural Coatings<br>(Amended June 3, 2022)</p></td>
  </tr>
  <tr>
    <td><p><a href="/docs/toc.pdf">Table of Contents</a> (PDF)</p></td>
    <td><p>Table of Contents</p></td>
  </tr>
</table>
</body></html>
"""


def test_scrape_regulation_page_finds_pdfs():
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = MOCK_REG_XI_HTML
    mock_resp.raise_for_status = MagicMock()
    mock_session.get.return_value = mock_resp

    rules = scraper.scrape_regulation_page(mock_session, "/regulation-xi", "XI", "Source Specific")

    # Should find 2 rules (not the TOC)
    assert len(rules) == 2


def test_scrape_regulation_page_extracts_rule_numbers():
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = MOCK_REG_XI_HTML
    mock_resp.raise_for_status = MagicMock()
    mock_session.get.return_value = mock_resp

    rules = scraper.scrape_regulation_page(mock_session, "/regulation-xi", "XI", "Source Specific")
    rule_numbers = [r["rule_number"] for r in rules]
    assert "1103" in rule_numbers
    assert "1113" in rule_numbers


def test_scrape_regulation_page_extracts_amendment_dates():
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = MOCK_REG_XI_HTML
    mock_resp.raise_for_status = MagicMock()
    mock_session.get.return_value = mock_resp

    rules = scraper.scrape_regulation_page(mock_session, "/regulation-xi", "XI", "Source Specific")
    rule_map = {r["rule_number"]: r for r in rules}
    assert "2023" in rule_map.get("1103", {}).get("amendment_date", "")


def test_scrape_regulation_page_skips_toc():
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = MOCK_REG_XI_HTML
    mock_resp.raise_for_status = MagicMock()
    mock_session.get.return_value = mock_resp

    rules = scraper.scrape_regulation_page(mock_session, "/regulation-xi", "XI", "Source Specific")
    urls = [r["pdf_url"] for r in rules]
    assert not any("toc" in u for u in urls)


def test_scrape_regulation_page_handles_network_error():
    mock_session = MagicMock()
    mock_session.get.side_effect = Exception("Connection timeout")

    rules = scraper.scrape_regulation_page(mock_session, "/regulation-xi", "XI", "Source Specific")
    assert rules == []


def test_scrape_regulation_page_deduplicates_urls():
    # Same PDF linked twice
    html = """<html><body>
    <a href="/docs/rule-1103.pdf">Rule 1103</a>
    <a href="/docs/rule-1103.pdf">Rule 1103 again</a>
    </body></html>"""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()
    mock_session.get.return_value = mock_resp

    rules = scraper.scrape_regulation_page(mock_session, "/test", "XI", "Source Specific")
    assert len(rules) == 1


def test_scrape_sets_correct_regulation_info():
    html = """<html><body>
    <a href="/docs/rule-401.pdf">Rule 401 Visible Emissions (Amended 2001)</a>
    </body></html>"""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()
    mock_session.get.return_value = mock_resp

    rules = scraper.scrape_regulation_page(mock_session, "/regulation-iv", "IV", "Prohibitions")
    assert rules[0]["regulation_num"] == "IV"
    assert rules[0]["regulation_name"] == "Prohibitions"


# ── REGULATION_PAGES completeness ──────────────────────

def test_regulation_pages_all_have_required_fields():
    for path, reg_num, reg_name in scraper.REGULATION_PAGES:
        assert path.startswith("/"), f"Path should be relative: {path}"
        assert reg_num, f"Missing regulation number for {path}"
        assert reg_name, f"Missing regulation name for {path}"


def test_regulation_pages_no_duplicates():
    paths = [p for p, _, _ in scraper.REGULATION_PAGES]
    assert len(paths) == len(set(paths)), "Duplicate regulation paths found"


def test_regulation_pages_count():
    # We expect at least 20 regulation pages
    assert len(scraper.REGULATION_PAGES) >= 20
