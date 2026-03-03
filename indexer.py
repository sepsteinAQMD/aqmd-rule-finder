"""
Downloads rule PDFs and indexes their text content into SQLite.
Runs in a background thread and reports progress via a callback.
"""

import os
import re
import time
import logging
import threading
import requests

import database
import scraper as scraper_module

logger = logging.getLogger(__name__)

# Global state for indexing progress (thread-safe via threading.Lock)
_lock = threading.Lock()
_state = {
    "running": False,
    "phase": "idle",          # idle | scanning | downloading | done | error
    "message": "",
    "current": 0,
    "total": 0,
    "errors": [],
    "last_completed": None,
}


def get_status():
    with _lock:
        return dict(_state)


def _update_state(**kwargs):
    with _lock:
        _state.update(kwargs)


def _progress_cb(current, total, message):
    _update_state(current=current, total=total, message=message)


def download_pdf(pdf_url, dest_path, session=None):
    """
    Download a PDF to dest_path. Returns True on success, False on failure.
    Skips download if file already exists and seems valid (size > 1KB).
    """
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024:
        return True

    if session is None:
        session = scraper_module.make_session()

    try:
        resp = session.get(pdf_url, timeout=60, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        # Accept PDF or binary content
        if "html" in content_type and "pdf" not in content_type:
            logger.warning(f"Unexpected content type for {pdf_url}: {content_type}")
            return False

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        if os.path.getsize(dest_path) < 512:
            os.remove(dest_path)
            logger.warning(f"Downloaded file too small, likely an error page: {pdf_url}")
            return False

        return True
    except Exception as e:
        logger.error(f"Failed to download {pdf_url}: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


def extract_pdf_text(pdf_path):
    """
    Extract text from a PDF, page by page.
    Returns list of (page_number: int, text: str) tuples.
    Uses PyMuPDF (fitz).
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF not installed. Run: pip install pymupdf")
        return []

    pages = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            # Clean up whitespace while preserving paragraph structure
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r'[ \t]+', ' ', text)
            text = text.strip()
            if text:
                pages.append((page_num + 1, text))
        doc.close()
    except Exception as e:
        logger.error(f"Failed to extract text from {pdf_path}: {e}")

    return pages


def _safe_filename(pdf_url):
    """Convert a PDF URL to a safe local filename."""
    filename = pdf_url.split("/")[-1]
    # Remove query strings
    filename = filename.split("?")[0]
    # Replace unsafe chars
    filename = re.sub(r'[^\w\-\.]', '_', filename)
    return filename[:200]  # limit length


def run_indexing(on_complete=None):
    """
    Main indexing function. Should be called in a background thread.
    1. Scrapes all regulation pages to discover rules
    2. Upserts rules into DB
    3. Downloads any un-indexed PDFs
    4. Extracts and indexes text
    """
    _update_state(running=True, phase="scanning", message="Connecting to AQMD website...", errors=[], current=0, total=0)

    db_path = database.get_db_path()
    pdf_dir = database.get_pdf_dir()

    try:
        # Phase 1: Scrape rule listings
        _update_state(phase="scanning", message="Scanning AQMD Rule Book pages...")
        all_rules = scraper_module.scrape_all_regulations(progress_cb=_progress_cb)

        if not all_rules:
            _update_state(
                running=False, phase="error",
                message="Could not fetch rule listings from AQMD website. Check your internet connection."
            )
            return

        # Phase 2: Update database with discovered rules
        _update_state(phase="scanning", message=f"Updating database with {len(all_rules)} discovered rules...")
        with database.get_connection(db_path) as conn:
            for rule in all_rules:
                database.upsert_rule(
                    conn,
                    rule_number=rule["rule_number"],
                    title=rule["title"],
                    regulation_num=rule["regulation_num"],
                    regulation_name=rule["regulation_name"],
                    pdf_url=rule["pdf_url"],
                    amendment_date=rule["amendment_date"],
                )

        # Phase 3: Download and index PDFs
        pending = database.get_rules_needing_download(db_path)
        total_pending = len(pending)
        _update_state(phase="downloading", message=f"Indexing {total_pending} rules...", total=total_pending, current=0)

        if total_pending == 0:
            _update_state(phase="done", running=False, message="All rules are up to date.", last_completed=_now())
            if on_complete:
                on_complete()
            return

        session = scraper_module.make_session()
        errors = []

        for i, rule in enumerate(pending):
            msg = f"Downloading Rule {rule['rule_number']}: {rule['title'][:60]}..."
            _update_state(current=i + 1, total=total_pending, message=msg)

            filename = _safe_filename(rule["pdf_url"])
            dest_path = os.path.join(pdf_dir, filename)

            # Download
            ok = download_pdf(rule["pdf_url"], dest_path, session=session)
            if not ok:
                err_msg = f"Download failed: {rule['pdf_url']}"
                errors.append(err_msg)
                with database.get_connection(db_path) as conn:
                    database.mark_rule_error(conn, rule["id"], err_msg)
                _update_state(errors=list(errors))
                continue

            # Extract text
            pages = extract_pdf_text(dest_path)
            if not pages:
                err_msg = f"No text extracted from: {filename}"
                errors.append(err_msg)
                with database.get_connection(db_path) as conn:
                    database.mark_rule_error(conn, rule["id"], err_msg)
                _update_state(errors=list(errors))
                continue

            # Index into database
            with database.get_connection(db_path) as conn:
                database.delete_rule_pages(conn, rule["id"])
                for page_num, content in pages:
                    database.insert_page(conn, rule["id"], page_num, content)
                database.mark_rule_downloaded(conn, rule["id"], filename, len(pages))
                database.mark_rule_indexed(conn, rule["id"])

            # Small delay to avoid hammering the server
            time.sleep(0.3)

        # Done
        database.set_app_state("last_full_update", _now(), db_path)
        stats = database.get_stats(db_path)
        final_msg = (
            f"Ready. {stats['indexed_rules']} of {stats['total_rules']} rules indexed "
            f"({stats['total_pages']} pages searchable)."
        )
        if errors:
            final_msg += f" {len(errors)} rules could not be downloaded."

        _update_state(
            running=False, phase="done",
            message=final_msg,
            last_completed=_now(),
            errors=errors,
        )

        if on_complete:
            on_complete()

    except Exception as e:
        logger.exception("Indexing failed with unhandled exception")
        _update_state(
            running=False, phase="error",
            message=f"Indexing error: {str(e)}"
        )


def start_indexing_thread(on_complete=None):
    """Start the indexing process in a background daemon thread."""
    with _lock:
        if _state["running"]:
            logger.info("Indexing already in progress, skipping.")
            return None

    t = threading.Thread(target=run_indexing, args=(on_complete,), daemon=True, name="AQMDIndexer")
    t.start()
    return t


def _now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
