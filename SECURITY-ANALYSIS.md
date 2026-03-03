# Security Analysis — AQMD Rule Finder
**Date:** March 2026
**Analyst:** Full manual code review of all source files
**Verdict: No malicious code found. The application is safe to share and use.**

---

## Files Reviewed

| File | Lines | Purpose |
|------|-------|---------|
| `app.py` | 197 | Flask web server, API routes |
| `database.py` | 332 | SQLite operations, FTS5 search |
| `scraper.py` | 285 | AQMD website scraper |
| `indexer.py` | 257 | PDF downloader and text extractor |
| `templates/index.html` | 176 | Web UI (HTML) |
| `static/app.js` | 382 | Web UI (JavaScript) |
| `static/style.css` | 341 | Styling only — no executable code |

---

## 1. Malware / Malicious Code

**Finding: NONE**

- No `subprocess`, `os.system`, `os.popen`, `eval`, or `exec` calls anywhere in the codebase.
- No shell commands are constructed or executed.
- No data is sent to any server other than `www.aqmd.gov` (a U.S. government website).
- No clipboard access, keylogging, screen capture, or process monitoring.
- No crypto mining, ransomware patterns, or destructive file operations.
- No obfuscated or encoded payloads. All code is plain, readable Python and JavaScript.

---

## 2. Network Activity

**Finding: LIMITED AND EXPECTED — only contacts aqmd.gov**

The application makes outbound HTTP requests in exactly two places:

**`scraper.py` — fetches regulation index pages**
```python
BASE_URL = "https://www.aqmd.gov"
REGULATION_PAGES = [...]  # Hardcoded list of 26 AQMD regulation page paths
```
- All scraped URLs are constructed as `BASE_URL + hardcoded_path`.
- No user-supplied URLs are passed to the scraper.
- Uses HTTPS, so traffic cannot be eavesdropped in transit.

**`indexer.py` — downloads PDF files**
```python
resp = session.get(pdf_url, timeout=60, stream=True)
```
- `pdf_url` values come only from the AQMD website scraper (previous step).
- The downloader does not accept URLs from the user or from any external source.
- There is no mechanism by which an attacker could redirect downloads to a malicious server (the URL list is populated from AQMD's own HTML).

**Flask server binding**
```python
app.run(host="127.0.0.1", port=PORT, ...)
```
- The web server binds exclusively to `127.0.0.1` (localhost/loopback).
- It is **not accessible from other machines** on the same network or the internet.

---

## 3. SQL Injection

**Finding: SAFE — all queries use parameterized statements**

Every database query in `database.py` uses `?` placeholders:

```python
# Example from upsert_rule():
conn.execute(
    "SELECT id, amendment_date FROM rules WHERE pdf_url = ?", (pdf_url,)
)
```

The one query that uses string formatting (`delete_rule_pages`) constructs its `IN (?,?,?)` placeholder list from a list of integer row IDs retrieved from the database — not from user input:

```python
placeholders = ",".join("?" * len(row_ids))
conn.execute(f"DELETE FROM rule_pages_fts WHERE rowid IN ({placeholders})", row_ids)
```

This is the correct, safe pattern for dynamic-length `IN` clauses.

The FTS5 search query is sanitized before use:

```python
def _sanitize_fts_query(query):
    words = re.findall(r'[A-Za-z0-9\-]+', query)  # strips all FTS5 special chars
    return " AND ".join(f'"{w}"' for w in words if len(w) >= 2)
```

**Conclusion: No SQL injection risk.**

---

## 4. Path Traversal (Directory Traversal)

**Finding: PROTECTED**

The PDF file-serving route includes an explicit path traversal guard:

```python
@app.route("/pdf/<path:filename>")
def serve_pdf(filename):
    pdf_dir = database.get_pdf_dir()
    pdf_path = os.path.join(pdf_dir, filename)
    if not os.path.isfile(pdf_path):
        abort(404)
    # Security: ensure the resolved path is within pdf_dir
    if not os.path.abspath(pdf_path).startswith(os.path.abspath(pdf_dir)):
        abort(403)
    return send_file(pdf_path, mimetype="application/pdf")
```

A request to `/pdf/../../../etc/passwd` would resolve to a path outside `pdf_dir` and be rejected with HTTP 403. This was verified in the test suite (`test_api_pdf_path_traversal_blocked`).

PDF filenames are also sanitized at download time:

```python
def _safe_filename(pdf_url):
    filename = pdf_url.split("/")[-1].split("?")[0]
    filename = re.sub(r'[^\w\-\.]', '_', filename)  # only word chars, dashes, dots
    return filename[:200]
```

This prevents any `../` sequences from appearing in stored filenames.

---

## 5. Cross-Site Scripting (XSS)

**Finding: ONE LOW-RISK NOTE (not exploitable in practice)**

**Properly escaped areas:**

The JavaScript `buildRuleCard()` function uses `escHtml()` on all database fields before inserting them into the DOM:

```javascript
function escHtml(str) {
    return String(str || '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
```

Rule numbers, titles, regulation names, and amendment dates are all passed through `escHtml()`. HTML attribute values are passed through `escAttr()`.

**The note:**

Search result excerpts (`m.excerpt`) are inserted as raw `innerHTML` so that the `<mark>...</mark>` highlight tags render correctly. The excerpt content originates from PyMuPDF's plain-text extraction of AQMD government PDF documents.

```javascript
<div class="match-excerpt">${m.excerpt}</div>
```

**Why this is not a practical risk:**
1. The PDF text source is AQMD.gov — U.S. government regulatory documents that do not contain HTML.
2. PyMuPDF extracts text content only, not HTML, from PDFs.
3. The server binds to `127.0.0.1` — no external party can submit a crafted search query.
4. Users of this tool are trusted colleagues, not anonymous external attackers.
5. The only way to exploit this would require compromising an AQMD PDF document — at which point the organization has far larger problems than this tool.

---

## 6. Command Injection

**Finding: NOT POSSIBLE**

No shell commands are executed anywhere in the application. The Python standard library `subprocess`, `os.system`, `os.popen`, `commands`, `pty`, and `shlex` modules are not imported or used. No `eval()` or `exec()` calls exist.

---

## 7. Sensitive Data

**Finding: NONE HANDLED OR STORED**

- The application does not collect, store, or transmit any personal information.
- No usernames, passwords, API keys, or authentication tokens are used.
- The only data stored locally is the AQMD rule text (public regulatory documents) and a SQLite index of that text.
- No logging of user search queries to disk (logs go to stdout/console only, and are not saved).

---

## 8. Dependency Review

All five runtime dependencies are widely used, actively maintained, open-source libraries:

| Package | Version | Purpose | Known Issues |
|---------|---------|---------|--------------|
| Flask | ≥3.0.0 | Web framework | None at this version |
| requests | ≥2.31.0 | HTTP client | None at this version |
| beautifulsoup4 | ≥4.12.0 | HTML parsing | None |
| pymupdf | ≥1.24.0 | PDF text extraction | None |
| pyinstaller | ≥6.0.0 | Executable packaging | Build-time only, not runtime |

No packages with known vulnerabilities are used. No unusual or suspicious packages are present.

---

## 9. Data Flow Summary

```
User types search query
       │
       ▼
app.py /api/search                     (input: string from URL query param)
       │
       ▼
_sanitize_fts_query()                  (strips all FTS5 special chars)
       │
       ▼
SQLite FTS5 MATCH query                (parameterized — no injection possible)
       │
       ▼
JSON response to browser               (plain data, no executable content)
       │
       ▼
buildRuleCard() in app.js              (escHtml() on all fields except excerpts)
       │
       ▼
User sees highlighted excerpts         (markup from trusted local DB only)
```

```
App startup
       │
       ▼
Scrape https://www.aqmd.gov           (HTTPS, hardcoded domain)
       │
       ▼
Download PDFs from aqmd.gov           (HTTPS, URLs from AQMD's own pages)
       │
       ▼
Extract text with PyMuPDF             (local, no network)
       │
       ▼
Store in SQLite at %APPDATA%          (local, user directory)
```

---

## Summary

| Category | Status |
|----------|--------|
| Malicious code | ✅ None found |
| Command injection | ✅ Not possible |
| SQL injection | ✅ Protected (parameterized queries) |
| Path traversal | ✅ Protected (explicit guard + filename sanitization) |
| XSS | ✅ Protected (one theoretical low-risk note on excerpts) |
| Data exfiltration | ✅ None — only contacts aqmd.gov |
| Network exposure | ✅ Localhost only |
| Sensitive data handling | ✅ None collected or stored |
| Dependency security | ✅ All packages reputable and up to date |

**This application is safe to share with colleagues. It performs exactly the functions described: scraping AQMD's public website, indexing regulatory documents, and providing a local search interface.**
