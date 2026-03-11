"""
AQMD Rule Finder — Flask application.
Serves the web UI and API endpoints for searching AQMD rules.
"""

import os
import sys
import json
import logging
import threading
import webbrowser
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file, Response, abort

import database
import indexer

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
# When packaged with PyInstaller the template/static dirs are next to the exe
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)

PORT = int(os.environ.get("AQMD_PORT", "5731"))


# ---------------------------------------------------------------------------
# Routes — UI
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------

@app.route("/api/status")
def api_status():
    """Combined indexing progress + database stats."""
    progress = indexer.get_status()
    stats = database.get_stats()
    return jsonify({**stats, **progress})


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    try:
        limit = max(1, min(500, int(request.args.get("limit", 50))))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        limit, offset = 50, 0

    if not query:
        return jsonify({"results": [], "total": 0, "query": ""})

    results = database.search_rules(query, limit=limit, offset=offset)
    return jsonify(results)


@app.route("/api/rules")
def api_rules():
    """List all rules (paginated), optionally filtered by regulation."""
    try:
        limit = max(1, min(500, int(request.args.get("limit", 100))))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        limit, offset = 100, 0
    regulation = request.args.get("regulation", "").strip()

    db_path = database.get_db_path()
    with database.get_connection(db_path) as conn:
        if regulation:
            rows = conn.execute(
                "SELECT * FROM rules WHERE regulation_num=? ORDER BY rule_number LIMIT ? OFFSET ?",
                (regulation, limit, offset),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM rules WHERE regulation_num=?", (regulation,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT * FROM rules ORDER BY regulation_num, rule_number LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0]

    return jsonify({
        "rules": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Trigger a background re-scan and re-index."""
    status = indexer.get_status()
    if status["running"]:
        return jsonify({"message": "Indexing already in progress.", "started": False})

    indexer.start_indexing_thread()
    return jsonify({"message": "Update started.", "started": True})


@app.route("/api/progress/stream")
def api_progress_stream():
    """
    Server-Sent Events stream for real-time indexing progress.
    The client connects once and receives updates every second.
    """
    def generate():
        import time
        last_state = None
        while True:
            state = indexer.get_status()
            stats = database.get_stats()
            combined = {**stats, **state}
            if combined != last_state:
                yield f"data: {json.dumps(combined)}\n\n"
                last_state = dict(combined)
            time.sleep(1)
            # Stop streaming if done
            if state.get("phase") in ("done", "error", "idle") and last_state is not None:
                # Send one final update then keep alive (client reconnects)
                yield f"data: {json.dumps({**combined, 'final': True})}\n\n"
                time.sleep(5)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/pdf/<path:filename>")
def serve_pdf(filename):
    """Serve a locally cached PDF file."""
    pdf_dir = database.get_pdf_dir()
    pdf_path = os.path.join(pdf_dir, filename)
    if not os.path.isfile(pdf_path):
        abort(404)
    # Security: ensure the resolved path is within pdf_dir
    if not os.path.abspath(pdf_path).startswith(os.path.abspath(pdf_dir)):
        abort(403)
    return send_file(pdf_path, mimetype="application/pdf")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def open_browser():
    """Open the default browser after a short delay to let Flask start."""
    import time
    time.sleep(1.5)
    webbrowser.open(f"http://127.0.0.1:{PORT}")


def main():
    # Initialise database
    database.init_db()

    # Start background indexing immediately on launch
    indexer.start_indexing_thread()

    # Open browser (unless running tests or in a non-interactive environment)
    if not os.environ.get("AQMD_NO_BROWSER"):
        t = threading.Thread(target=open_browser, daemon=True)
        t.start()

    logger.info(f"AQMD Rule Finder running at http://127.0.0.1:{PORT}")
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
