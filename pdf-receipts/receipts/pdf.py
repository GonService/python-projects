"""PDF layout with ReportLab: one A4 page per receipt, with a copy for the payer and one for the issuer."""

from __future__ import annotations

import io
from collections.abc import Iterable
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from . import __version__
from .documents import kind
from .model import Receipt

INK = HexColor("#1f2a30")
MUTED = HexColor("#5d6b73")
ACCENT = HexColor("#24506b")
LINE = HexColor("#c9d2d8")
TINT = HexColor("#eef3f6")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=11.5, leading=18, textColor=INK)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=10, leading=14, textColor=MUTED)


def _doc_label(document: str) -> str:
    return f"{kind(document) or 'Documento'} {document}" if document else ""


def _copy(c: Canvas, r: Receipt, top: float, height: float, label: str) -> None:
    left, right = MARGIN, PAGE_W - MARGIN
    width = right - left

    # Header: issuer on the left, title and amount on the right.
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(left, top - 6 * mm, r.issuer)
    c.setFont("Helvetica", 9.5)
    c.setFillColor(MUTED)
    c.drawString(left, top - 11 * mm, _doc_label(r.issuer_document))
    c.drawString(left, top - 15.5 * mm, r.city)

    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 22)
    c.drawRightString(right, top - 8 * mm, "RECIBO")
    c.setFont("Helvetica", 10)
    c.setFillColor(MUTED)
    c.drawRightString(right, top - 13.5 * mm, f"Nº {r.number}")

    box_w, box_h = 62 * mm, 12 * mm
    box_y = top - 32 * mm
    c.setFillColor(TINT)
    c.setStrokeColor(ACCENT)
    c.setLineWidth(0.8)
    c.roundRect(right - box_w, box_y, box_w, box_h, 2 * mm, stroke=1, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 15)
    c.drawRightString(right - 4 * mm, box_y + 4 * mm, r.amount_brl)
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    c.drawString(right - box_w + 3 * mm, box_y + 4.6 * mm, "VALOR")

    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(left, box_y - 5 * mm, right, box_y - 5 * mm)

    # Body text.
    company = kind(r.issuer_document) == "CNPJ"
    verb, sign = ("Recebemos", "firmamos") if company else ("Recebi", "firmo")
    payer = f"<b>{escape(r.payer)}</b>"
    if r.payer_document:
        payer += f", {escape(_doc_label(r.payer_document))}"
    text = (
        f"{verb} de {payer}, a importância de <b>{r.amount_brl}</b> ({escape(r.amount_words)}), "
        f"referente a <b>{escape(r.description)}</b>."
    )
    y = box_y - 10 * mm
    for content, style in (
        (text, BODY),
        (f"Forma de pagamento: {escape(r.payment_method)}." if r.payment_method else "", SMALL),
        (f"Para maior clareza, {sign} o presente recibo, dando plena quitação do valor recebido.", SMALL),
    ):
        if not content:
            continue
        p = Paragraph(content, style)
        _, h = p.wrap(width, height)
        p.drawOn(c, left, y - h)
        y -= h + 3 * mm

    # Place, date and signature.
    bottom = top - height
    c.setFont("Helvetica", 11)
    c.setFillColor(INK)
    c.drawRightString(right, bottom + 34 * mm, f"{r.city}, {r.date_long}.")
    sig_w = 85 * mm
    sig_x = right - sig_w
    c.setStrokeColor(INK)
    c.line(sig_x, bottom + 17 * mm, right, bottom + 17 * mm)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(sig_x + sig_w / 2, bottom + 12.5 * mm, r.issuer)
    c.setFont("Helvetica", 9)
    c.setFillColor(MUTED)
    c.drawCentredString(sig_x + sig_w / 2, bottom + 8.5 * mm, _doc_label(r.issuer_document))
    c.setFont("Helvetica", 8)
    c.drawString(left, bottom + 8.5 * mm, label.upper())


def render(receipts: Iterable[Receipt], compress: bool = True) -> bytes:
    """All receipts in one PDF, one page each."""
    buffer = io.BytesIO()
    c = Canvas(buffer, pagesize=A4, pageCompression=1 if compress else 0, invariant=not compress)
    c.setCreator(f"pdf-receipts {__version__}")
    count = 0
    for r in receipts:
        count += 1
        c.setTitle(f"Recibo {r.number}")
        half = (PAGE_H - 2 * MARGIN) / 2
        _copy(c, r, PAGE_H - MARGIN, half - 6 * mm, "Via do pagador")
        # dashed cut line between the two copies
        c.setDash(4, 3)
        c.setStrokeColor(LINE)
        c.line(MARGIN, PAGE_H / 2, PAGE_W - MARGIN, PAGE_H / 2)
        c.setDash()
        _copy(c, r, PAGE_H / 2 - 6 * mm, half - 6 * mm, "Via do emitente")
        c.showPage()
    if not count:
        raise ValueError("no receipts to render")
    c.save()
    return buffer.getvalue()
