"""
SQLite database operations for AQMD Rule Finder.
Uses FTS5 for full-text search across rule PDF content.
"""

import sqlite3
import os
from contextlib import contextmanager


def get_db_path():
    data_dir = os.environ.get("AQMD_DATA_DIR", os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "AQMDRuleFinder"))
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "rules.db")


def get_pdf_dir():
    data_dir = os.environ.get("AQMD_DATA_DIR", os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "AQMDRuleFinder"))
    pdf_dir = os.path.join(data_dir, "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    return pdf_dir


@contextmanager
def get_connection(db_path=None):
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path=None):
    """Create all tables if they don't exist."""
    if db_path is None:
        db_path = get_db_path()
    with get_connection(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_number TEXT NOT NULL,
                title TEXT NOT NULL,
                regulation_num TEXT NOT NULL,
                regulation_name TEXT,
                pdf_url TEXT NOT NULL UNIQUE,
                local_filename TEXT,
                amendment_date TEXT,
                last_downloaded TEXT,
                is_indexed INTEGER DEFAULT 0,
                page_count INTEGER DEFAULT 0,
                download_error TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_rules_regulation ON rules(regulation_num);
            CREATE INDEX IF NOT EXISTS idx_rules_rule_number ON rules(rule_number);

            CREATE TABLE IF NOT EXISTS rule_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER NOT NULL,
                page_number INTEGER NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY (rule_id) REFERENCES rules(id) ON DELETE CASCADE
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS rule_pages_fts USING fts5(
                content,
                content=rule_pages,
                content_rowid=id
            );

            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)


def upsert_rule(conn, rule_number, title, regulation_num, regulation_name, pdf_url, amendment_date):
    """Insert or update a rule record. Returns the rule id."""
    existing = conn.execute(
        "SELECT id, amendment_date FROM rules WHERE pdf_url = ?", (pdf_url,)
    ).fetchone()

    if existing:
        if existing["amendment_date"] != amendment_date:
            # Amendment date changed — mark for re-download
            conn.execute(
                """UPDATE rules SET rule_number=?, title=?, regulation_num=?, regulation_name=?,
                   amendment_date=?, is_indexed=0, last_downloaded=NULL, download_error=NULL
                   WHERE pdf_url=?""",
                (rule_number, title, regulation_num, regulation_name, amendment_date, pdf_url),
            )
        return existing["id"]
    else:
        cursor = conn.execute(
            """INSERT INTO rules (rule_number, title, regulation_num, regulation_name, pdf_url, amendment_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (rule_number, title, regulation_num, regulation_name, pdf_url, amendment_date),
        )
        return cursor.lastrowid


def mark_rule_downloaded(conn, rule_id, local_filename, page_count):
    conn.execute(
        "UPDATE rules SET local_filename=?, last_downloaded=datetime('now'), download_error=NULL, page_count=? WHERE id=?",
        (local_filename, page_count, rule_id),
    )


def mark_rule_error(conn, rule_id, error_msg):
    conn.execute(
        "UPDATE rules SET download_error=? WHERE id=?",
        (error_msg, rule_id),
    )


def mark_rule_indexed(conn, rule_id):
    conn.execute("UPDATE rules SET is_indexed=1 WHERE id=?", (rule_id,))


def delete_rule_pages(conn, rule_id):
    """Remove old page content before re-indexing."""
    row_ids = [r["id"] for r in conn.execute(
        "SELECT id FROM rule_pages WHERE rule_id=?", (rule_id,)
    ).fetchall()]
    if row_ids:
        placeholders = ",".join("?" * len(row_ids))
        conn.execute(f"DELETE FROM rule_pages_fts WHERE rowid IN ({placeholders})", row_ids)
        conn.execute("DELETE FROM rule_pages WHERE rule_id=?", (rule_id,))


def insert_page(conn, rule_id, page_number, content):
    cursor = conn.execute(
        "INSERT INTO rule_pages (rule_id, page_number, content) VALUES (?, ?, ?)",
        (rule_id, page_number, content),
    )
    row_id = cursor.lastrowid
    conn.execute("INSERT INTO rule_pages_fts(rowid, content) VALUES (?, ?)", (row_id, content))
    return row_id


def search_rules(query, limit=50, offset=0, db_path=None):
    """
    Full-text search across all indexed rule pages.
    Returns list of dicts with rule info and matched excerpts.
    """
    if db_path is None:
        db_path = get_db_path()

    # Sanitize query for FTS5 — escape special characters
    safe_query = _sanitize_fts_query(query)
    if not safe_query:
        return {"results": [], "total": 0, "query": query}

    with get_connection(db_path) as conn:
        try:
            rows = conn.execute(
                """
                SELECT
                    r.id, r.rule_number, r.title, r.regulation_num, r.regulation_name,
                    r.pdf_url, r.local_filename, r.amendment_date, r.page_count,
                    rp.page_number,
                    snippet(rule_pages_fts, 0, '<mark>', '</mark>', '...', 40) AS excerpt,
                    rank
                FROM rule_pages_fts
                JOIN rule_pages rp ON rp.id = rule_pages_fts.rowid
                JOIN rules r ON r.id = rp.rule_id
                WHERE rule_pages_fts MATCH ?
                ORDER BY rank
                LIMIT ? OFFSET ?
                """,
                (safe_query, limit, offset),
            ).fetchall()

            count_row = conn.execute(
                """
                SELECT COUNT(*) as cnt
                FROM rule_pages_fts
                JOIN rule_pages rp ON rp.id = rule_pages_fts.rowid
                JOIN rules r ON r.id = rp.rule_id
                WHERE rule_pages_fts MATCH ?
                """,
                (safe_query,),
            ).fetchone()

            total = count_row["cnt"] if count_row else 0

            results = []
            seen_rules = {}  # rule_id -> index in results for deduplication within same rule
            for row in rows:
                rule_id = row["id"]
                entry = {
                    "rule_id": rule_id,
                    "rule_number": row["rule_number"],
                    "title": row["title"],
                    "regulation_num": row["regulation_num"],
                    "regulation_name": row["regulation_name"],
                    "pdf_url": row["pdf_url"],
                    "local_filename": row["local_filename"],
                    "amendment_date": row["amendment_date"],
                    "page_count": row["page_count"],
                    "matches": [{"page": row["page_number"], "excerpt": row["excerpt"]}],
                }
                if rule_id in seen_rules:
                    # Add match to existing rule entry
                    results[seen_rules[rule_id]]["matches"].append(
                        {"page": row["page_number"], "excerpt": row["excerpt"]}
                    )
                else:
                    seen_rules[rule_id] = len(results)
                    results.append(entry)

            return {"results": results, "total": total, "query": query}

        except sqlite3.OperationalError as e:
            # FTS syntax error — fall back to LIKE search
            return _fallback_search(conn, query, limit, offset)


def _fallback_search(conn, query, limit, offset):
    """Simple LIKE-based search as fallback when FTS query is invalid."""
    like_pattern = f"%{query}%"
    rows = conn.execute(
        """
        SELECT r.id, r.rule_number, r.title, r.regulation_num, r.regulation_name,
               r.pdf_url, r.local_filename, r.amendment_date, r.page_count,
               rp.page_number, rp.content as excerpt
        FROM rule_pages rp
        JOIN rules r ON r.id = rp.rule_id
        WHERE rp.content LIKE ? OR r.title LIKE ?
        LIMIT ? OFFSET ?
        """,
        (like_pattern, like_pattern, limit, offset),
    ).fetchall()

    results = []
    for row in rows:
        excerpt = row["excerpt"]
        # Find the relevant portion of the text
        idx = excerpt.lower().find(query.lower())
        if idx >= 0:
            start = max(0, idx - 100)
            end = min(len(excerpt), idx + len(query) + 200)
            excerpt = ("..." if start > 0 else "") + excerpt[start:end] + ("..." if end < len(excerpt) else "")
            # Highlight the term
            excerpt = excerpt[:idx - start] + "<mark>" + excerpt[idx - start:idx - start + len(query)] + "</mark>" + excerpt[idx - start + len(query):]

        results.append({
            "rule_id": row["id"],
            "rule_number": row["rule_number"],
            "title": row["title"],
            "regulation_num": row["regulation_num"],
            "regulation_name": row["regulation_name"],
            "pdf_url": row["pdf_url"],
            "local_filename": row["local_filename"],
            "amendment_date": row["amendment_date"],
            "page_count": row["page_count"],
            "matches": [{"page": row["page_number"], "excerpt": excerpt}],
        })

    return {"results": results, "total": len(results), "query": query}


def _sanitize_fts_query(query):
    """Convert a plain text query into a safe FTS5 query."""
    # Strip leading/trailing whitespace
    query = query.strip()
    if not query:
        return ""

    # Remove FTS5 special characters that could cause syntax errors
    # Keep alphanumeric, spaces, hyphens
    import re
    words = re.findall(r'[A-Za-z0-9\-]+', query)
    if not words:
        return ""

    # Build a query that matches documents containing all the words
    return " AND ".join(f'"{w}"' for w in words if len(w) >= 2)


def get_stats(db_path=None):
    """Return indexing status statistics."""
    if db_path is None:
        db_path = get_db_path()
    try:
        with get_connection(db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
            indexed = conn.execute("SELECT COUNT(*) FROM rules WHERE is_indexed=1").fetchone()[0]
            failed = conn.execute("SELECT COUNT(*) FROM rules WHERE download_error IS NOT NULL").fetchone()[0]
            pages = conn.execute("SELECT COUNT(*) FROM rule_pages").fetchone()[0]
            last_update = conn.execute(
                "SELECT value FROM app_state WHERE key='last_full_update'"
            ).fetchone()
            return {
                "total_rules": total,
                "indexed_rules": indexed,
                "failed_rules": failed,
                "total_pages": pages,
                "last_update": last_update["value"] if last_update else None,
            }
    except Exception:
        return {"total_rules": 0, "indexed_rules": 0, "failed_rules": 0, "total_pages": 0, "last_update": None}


def set_app_state(key, value, db_path=None):
    if db_path is None:
        db_path = get_db_path()
    with get_connection(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)", (key, value))


def get_rules_needing_download(db_path=None):
    """Return rules that haven't been downloaded or need re-downloading."""
    if db_path is None:
        db_path = get_db_path()
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT id, rule_number, title, regulation_num, pdf_url
               FROM rules WHERE is_indexed=0 AND (download_error IS NULL OR last_downloaded IS NULL)"""
        ).fetchall()
        return [dict(r) for r in rows]
