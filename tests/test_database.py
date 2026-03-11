"""
Tests for database.py — SQLite schema and FTS5 search.
"""

import os
import sys
import tempfile
import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database for each test."""
    db_path = str(tmp_path / "test.db")
    os.environ["AQMD_DATA_DIR"] = str(tmp_path)
    database.init_db(db_path)
    return db_path


# ── init_db ────────────────────────────────────────────

def test_init_db_creates_tables(tmp_db):
    with database.get_connection(tmp_db) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "rules" in tables
    assert "rule_pages" in tables
    assert "app_state" in tables


def test_init_db_creates_fts_table(tmp_db):
    with database.get_connection(tmp_db) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "rule_pages_fts" in tables


def test_init_db_idempotent(tmp_db):
    """Calling init_db twice should not raise."""
    database.init_db(tmp_db)
    database.init_db(tmp_db)


# ── upsert_rule ────────────────────────────────────────

def test_upsert_rule_inserts_new(tmp_db):
    with database.get_connection(tmp_db) as conn:
        rule_id = database.upsert_rule(
            conn, "1103", "Pharmaceuticals Manufacturing", "XI", "Source Specific",
            "https://aqmd.gov/rule-1103.pdf", "January 6, 2023"
        )
    assert isinstance(rule_id, int)
    assert rule_id > 0


def test_upsert_rule_returns_same_id_for_duplicate(tmp_db):
    url = "https://aqmd.gov/rule-401.pdf"
    with database.get_connection(tmp_db) as conn:
        id1 = database.upsert_rule(conn, "401", "Visible Emissions", "IV", "Prohibitions", url, "2001")
        id2 = database.upsert_rule(conn, "401", "Visible Emissions", "IV", "Prohibitions", url, "2001")
    assert id1 == id2


def test_upsert_rule_marks_redownload_on_date_change(tmp_db):
    url = "https://aqmd.gov/rule-401.pdf"
    with database.get_connection(tmp_db) as conn:
        rule_id = database.upsert_rule(conn, "401", "Visible Emissions", "IV", "Prohibitions", url, "2001")
        # Simulate: mark as indexed
        conn.execute("UPDATE rules SET is_indexed=1 WHERE id=?", (rule_id,))
    # Now upsert with a new amendment date
    with database.get_connection(tmp_db) as conn:
        same_id = database.upsert_rule(conn, "401", "Visible Emissions", "IV", "Prohibitions", url, "2024")
        row = conn.execute("SELECT is_indexed FROM rules WHERE id=?", (rule_id,)).fetchone()
    assert same_id == rule_id
    assert row["is_indexed"] == 0  # Should be reset for re-download


# ── mark_rule_downloaded ───────────────────────────────

def test_mark_rule_downloaded(tmp_db):
    with database.get_connection(tmp_db) as conn:
        rule_id = database.upsert_rule(
            conn, "1103", "Test Rule", "XI", "Source Specific",
            "https://aqmd.gov/test.pdf", "2023"
        )
        database.mark_rule_downloaded(conn, rule_id, "test.pdf", 5)
        row = conn.execute("SELECT local_filename, page_count, download_error FROM rules WHERE id=?", (rule_id,)).fetchone()
    assert row["local_filename"] == "test.pdf"
    assert row["page_count"] == 5
    assert row["download_error"] is None


def test_mark_rule_error(tmp_db):
    with database.get_connection(tmp_db) as conn:
        rule_id = database.upsert_rule(
            conn, "999", "Missing Rule", "IV", "Prohibitions",
            "https://aqmd.gov/missing.pdf", ""
        )
        database.mark_rule_error(conn, rule_id, "HTTP 404")
        row = conn.execute("SELECT download_error FROM rules WHERE id=?", (rule_id,)).fetchone()
    assert row["download_error"] == "HTTP 404"


# ── insert_page / FTS search ───────────────────────────

def test_insert_page_and_search(tmp_db):
    with database.get_connection(tmp_db) as conn:
        rule_id = database.upsert_rule(
            conn, "1103", "Pharmaceuticals Manufacturing", "XI", "Source Specific",
            "https://aqmd.gov/rule-1103.pdf", "2023"
        )
        database.insert_page(conn, rule_id, 1, "This rule applies to pharmaceutical manufacturing operations.")
        database.insert_page(conn, rule_id, 2, "Equipment used in the synthesis of pharmaceutical compounds.")
        database.mark_rule_indexed(conn, rule_id)

    results = database.search_rules("pharmaceutical", db_path=tmp_db)
    assert results["total"] > 0
    assert len(results["results"]) > 0
    assert results["results"][0]["rule_number"] == "1103"


def test_search_returns_page_numbers(tmp_db):
    with database.get_connection(tmp_db) as conn:
        rule_id = database.upsert_rule(
            conn, "401", "Visible Emissions", "IV", "Prohibitions",
            "https://aqmd.gov/rule-401.pdf", "2001"
        )
        database.insert_page(conn, rule_id, 3, "No person shall discharge visible emissions.")
        database.mark_rule_indexed(conn, rule_id)

    results = database.search_rules("visible emissions", db_path=tmp_db)
    assert results["total"] > 0
    match = results["results"][0]["matches"][0]
    assert match["page"] == 3


def test_search_highlights_terms(tmp_db):
    with database.get_connection(tmp_db) as conn:
        rule_id = database.upsert_rule(
            conn, "1113", "Architectural Coatings", "XI", "Source Specific",
            "https://aqmd.gov/r1113.pdf", "2023"
        )
        database.insert_page(conn, rule_id, 1, "This rule limits VOC content in architectural coatings sold in the region.")
        database.mark_rule_indexed(conn, rule_id)

    results = database.search_rules("architectural coatings", db_path=tmp_db)
    excerpt = results["results"][0]["matches"][0]["excerpt"]
    assert "<mark>" in excerpt


def test_search_multiple_rules(tmp_db):
    with database.get_connection(tmp_db) as conn:
        for i, (num, title, content) in enumerate([
            ("401", "Visible Emissions", "No person shall discharge visible emissions from any source."),
            ("403", "Fugitive Dust", "This rule applies to fugitive dust from construction operations."),
            ("445", "Wood-Burning Devices", "Restrictions on wood-burning fireplace devices during curtailment periods."),
        ]):
            rule_id = database.upsert_rule(conn, num, title, "IV", "Prohibitions", f"https://aqmd.gov/rule-{num}.pdf", "2023")
            database.insert_page(conn, rule_id, 1, content)
            database.mark_rule_indexed(conn, rule_id)

    results = database.search_rules("emissions", db_path=tmp_db)
    assert results["total"] >= 1


def test_search_empty_query_returns_empty(tmp_db):
    results = database.search_rules("", db_path=tmp_db)
    assert results["total"] == 0
    assert results["results"] == []


def test_search_no_results(tmp_db):
    results = database.search_rules("xyznotfound12345", db_path=tmp_db)
    assert results["total"] == 0
    assert results["results"] == []


def test_search_special_chars_dont_crash(tmp_db):
    """FTS5 special characters should be sanitized, not raise exceptions."""
    for query in ['(', ')', '"', 'AND', 'OR', 'NOT', '*', ':', '--', '']:
        results = database.search_rules(query, db_path=tmp_db)
        assert isinstance(results, dict)


def test_delete_rule_pages(tmp_db):
    with database.get_connection(tmp_db) as conn:
        rule_id = database.upsert_rule(
            conn, "500", "Test Delete", "V", "Toxics",
            "https://aqmd.gov/rule-500.pdf", "2023"
        )
        database.insert_page(conn, rule_id, 1, "Some content about chemicals and toxics.")
        database.mark_rule_indexed(conn, rule_id)

    # Verify it's searchable
    assert database.search_rules("chemicals", db_path=tmp_db)["total"] > 0

    # Delete pages
    with database.get_connection(tmp_db) as conn:
        database.delete_rule_pages(conn, rule_id)

    # Should no longer be searchable
    assert database.search_rules("chemicals", db_path=tmp_db)["total"] == 0


# ── get_stats ──────────────────────────────────────────

def test_get_stats_empty_db(tmp_db):
    stats = database.get_stats(db_path=tmp_db)
    assert stats["total_rules"] == 0
    assert stats["indexed_rules"] == 0
    assert stats["total_pages"] == 0


def test_get_stats_with_data(tmp_db):
    with database.get_connection(tmp_db) as conn:
        rule_id = database.upsert_rule(
            conn, "1103", "Test", "XI", "Source Specific",
            "https://aqmd.gov/test.pdf", "2023"
        )
        database.insert_page(conn, rule_id, 1, "Sample content.")
        database.insert_page(conn, rule_id, 2, "More content.")
        database.mark_rule_indexed(conn, rule_id)

    stats = database.get_stats(db_path=tmp_db)
    assert stats["total_rules"] == 1
    assert stats["indexed_rules"] == 1
    assert stats["total_pages"] == 2


# ── get_rules_needing_download ─────────────────────────

def test_get_rules_needing_download(tmp_db):
    with database.get_connection(tmp_db) as conn:
        database.upsert_rule(conn, "401", "Rule A", "IV", "Prohibitions", "https://a.pdf", "2023")
        rid = database.upsert_rule(conn, "403", "Rule B", "IV", "Prohibitions", "https://b.pdf", "2023")
        conn.execute("UPDATE rules SET is_indexed=1 WHERE id=?", (rid,))

    pending = database.get_rules_needing_download(db_path=tmp_db)
    assert len(pending) == 1
    assert pending[0]["rule_number"] == "401"


# ── app_state ──────────────────────────────────────────

def test_set_and_get_app_state(tmp_db):
    database.set_app_state("last_full_update", "2024-01-01", db_path=tmp_db)
    with database.get_connection(tmp_db) as conn:
        row = conn.execute("SELECT value FROM app_state WHERE key='last_full_update'").fetchone()
    assert row["value"] == "2024-01-01"


def test_app_state_overwrite(tmp_db):
    database.set_app_state("key1", "value1", db_path=tmp_db)
    database.set_app_state("key1", "value2", db_path=tmp_db)
    with database.get_connection(tmp_db) as conn:
        row = conn.execute("SELECT value FROM app_state WHERE key='key1'").fetchone()
    assert row["value"] == "value2"


# ── _sanitize_fts_query ────────────────────────────────

def test_sanitize_fts_query_basic():
    result = database._sanitize_fts_query("pharmaceutical")
    assert "pharmaceutical" in result


def test_sanitize_fts_query_multi_word():
    result = database._sanitize_fts_query("auto body shop")
    assert "auto" in result
    assert "body" in result
    assert "shop" in result


def test_sanitize_fts_query_empty():
    assert database._sanitize_fts_query("") == ""
    assert database._sanitize_fts_query("   ") == ""


def test_sanitize_fts_query_special_chars():
    # Should not crash or return invalid FTS syntax
    result = database._sanitize_fts_query("(test) AND OR")
    assert isinstance(result, str)


# ── Synonym expansion ──────────────────────────────────

def test_sanitize_auto_body_shop_expands():
    """'auto body shop' should expand to include 'automotive refinishing'."""
    result = database._sanitize_fts_query("auto body shop")
    assert "automotive" in result
    assert "refinishing" in result
    # Original words must still be present
    assert "auto" in result
    assert "body" in result


def test_sanitize_gas_station_expands():
    """'gas station' should expand to include 'gasoline dispensing'."""
    result = database._sanitize_fts_query("gas station")
    assert "gasoline" in result
    assert "dispensing" in result


def test_sanitize_gas_stations_plural_expands():
    result = database._sanitize_fts_query("gas stations")
    assert "gasoline" in result
    assert "dispensing" in result


def test_sanitize_no_synonym_unchanged():
    """Terms without synonyms should produce a simple AND query with no OR."""
    result = database._sanitize_fts_query("boiler")
    assert "boiler" in result
    assert " OR " not in result


def test_sanitize_dry_cleaner_expands():
    result = database._sanitize_fts_query("dry cleaner")
    assert "perchloroethylene" in result


def test_sanitize_restaurant_expands():
    result = database._sanitize_fts_query("restaurant")
    assert "cooking" in result or "food" in result


def test_synonym_search_finds_automotive_refinishing(tmp_db):
    """Searching 'auto body shop' should find content about automotive refinishing."""
    with database.get_connection(tmp_db) as conn:
        rule_id = database.upsert_rule(
            conn, "1151", "Automotive Refinishing Operations", "XI", "Source Specific",
            "https://aqmd.gov/rule-1151.pdf", "2022"
        )
        database.insert_page(conn, rule_id, 1,
            "This rule applies to automotive refinishing operations including the "
            "application of coatings to motor vehicles.")
        database.mark_rule_indexed(conn, rule_id)

    results = database.search_rules("auto body shop", db_path=tmp_db)
    assert results["total"] > 0
    assert any(r["rule_number"] == "1151" for r in results["results"])


def test_synonym_search_finds_gasoline_dispensing(tmp_db):
    """Searching 'gas stations' should find content about gasoline dispensing."""
    with database.get_connection(tmp_db) as conn:
        rule_id = database.upsert_rule(
            conn, "461", "Gasoline Transfer and Dispensing", "IV", "Prohibitions",
            "https://aqmd.gov/rule-461.pdf", "2020"
        )
        database.insert_page(conn, rule_id, 1,
            "This rule applies to gasoline dispensing facilities including retail "
            "service stations and fleet fueling operations.")
        database.mark_rule_indexed(conn, rule_id)

    results = database.search_rules("gas stations", db_path=tmp_db)
    assert results["total"] > 0
    assert any(r["rule_number"] == "461" for r in results["results"])
