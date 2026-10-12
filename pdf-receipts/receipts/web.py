"""Flask app: a form that issues one receipt as PDF, plus a small JSON helper for the amount in words."""

from __future__ import annotations

import os
from datetime import date

from flask import Flask, Response, jsonify, render_template, request

from .documents import kind
from .extenso import reais_por_extenso
from .model import FIELDS, ReceiptError, build
from .money import parse_brl
from .pdf import render


def create_app(defaults: dict[str, str] | None = None) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    issuer = defaults or {
        "emitente": os.environ.get("ISSUER_NAME", ""),
        "documento_emitente": os.environ.get("ISSUER_DOCUMENT", ""),
        "cidade": os.environ.get("ISSUER_CITY", ""),
    }

    def form_page(values: dict[str, str], errors: dict[str, str] | None = None, status: int = 200):
        return render_template("form.html", v=values, errors=errors or {}), status

    @app.get("/")
    def index():
        return form_page({"data": date.today().strftime("%d/%m/%Y"), **issuer})

    @app.post("/recibo")
    def receipt():
        values = {k: request.form.get(k, "") for k in FIELDS}
        try:
            r = build(values)
        except ReceiptError as exc:
            return form_page(values, exc.errors, 422)
        disposition = "attachment" if request.form.get("download") else "inline"
        return Response(
            render([r]),
            mimetype="application/pdf",
            headers={"Content-Disposition": f'{disposition}; filename="{r.filename}"'},
        )

    @app.get("/api/extenso")
    def extenso():
        try:
            value = parse_brl(request.args.get("valor", ""))
            if value < 0:
                raise ValueError
            return jsonify(valor=str(value), extenso=reais_por_extenso(value))
        except ValueError:
            return jsonify(error="valor inválido"), 400

    @app.get("/api/documento")
    def documento():
        value = request.args.get("numero", "")
        return jsonify(numero=value, tipo=kind(value), valido=kind(value) is not None)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app
