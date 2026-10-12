"""Flask app: upload a sales spreadsheet, get a report (HTML, Excel or JSON)."""

from __future__ import annotations

import io
import os
import time
import uuid
from decimal import Decimal
from threading import Lock

from flask import Flask, abort, jsonify, render_template, request, send_file

from .report import ReportError, read_sales, summarize, to_xlsx

MAX_UPLOAD_MB = 5
CACHE_TTL_SECONDS = 15 * 60


class _ReportCache:
    """Keeps generated Excel files for a short time so the user can download them."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[float, bytes]] = {}
        self._lock = Lock()

    def put(self, data: bytes) -> str:
        key = uuid.uuid4().hex
        with self._lock:
            now = time.time()
            self._items = {k: v for k, v in self._items.items() if now - v[0] < CACHE_TTL_SECONDS}
            self._items[key] = (now, data)
        return key

    def get(self, key: str) -> bytes | None:
        with self._lock:
            item = self._items.get(key)
        if not item or time.time() - item[0] >= CACHE_TTL_SECONDS:
            return None
        return item[1]


def brl(value: Decimal | float | int) -> str:
    """1234.5 -> 'R$ 1.234,50'"""
    text = f"{Decimal(str(value)):,.2f}"
    return "R$ " + text.replace(",", "_").replace(".", ",").replace("_", ".")


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only")
    app.jinja_env.filters["brl"] = brl
    cache = _ReportCache()

    def _build(file_storage):
        if not file_storage or not file_storage.filename:
            raise ReportError("Choose a .csv or .xlsx file.")
        sales, skipped = read_sales(file_storage.filename, file_storage.read())
        summary = summarize(sales)
        summary.skipped_rows = skipped
        return summary

    @app.get("/")
    def index():
        return render_template("index.html", max_mb=MAX_UPLOAD_MB)

    @app.post("/report")
    def report():
        try:
            summary = _build(request.files.get("file"))
        except ReportError as exc:
            return render_template("index.html", max_mb=MAX_UPLOAD_MB, error=str(exc)), 400
        key = cache.put(to_xlsx(summary))
        peak = max(summary.by_month.values()) if summary.by_month else Decimal("1")
        return render_template("report.html", s=summary, download_key=key, peak=peak or Decimal("1"))

    @app.get("/report/<key>.xlsx")
    def download(key: str):
        data = cache.get(key)
        if data is None:
            abort(404, "This report expired. Upload the file again.")
        return send_file(
            io.BytesIO(data),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="sales-report.xlsx",
        )

    @app.post("/api/report")
    def api_report():
        try:
            summary = _build(request.files.get("file"))
        except ReportError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(summary.as_dict())

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.errorhandler(413)
    def too_large(_exc):
        message = f"The file is larger than {MAX_UPLOAD_MB} MB."
        if request.path.startswith("/api/"):
            return jsonify(error=message), 413
        return render_template("index.html", max_mb=MAX_UPLOAD_MB, error=message), 413

    return app
