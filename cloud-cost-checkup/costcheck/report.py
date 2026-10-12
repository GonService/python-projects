"""Output formats: self-contained HTML, JSON and a plain-text summary for the terminal."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import __version__
from .checks import Report

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def usd(value: float) -> str:
    return f"US$ {value:,.2f}"


_env.filters["usd"] = usd


def to_html(report: Report) -> str:
    sections = report.by_check()
    top = max((total for *_, total in sections), default=0) or 1
    return _env.get_template("report.html").render(r=report, sections=sections, top=top, version=__version__)


def to_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)


def to_text(report: Report, top: int = 5) -> str:
    lines = [
        f"AWS cost checkup - account {report.account_id} - {', '.join(report.regions)}",
        "",
        f"{'Check':<38}{'Items':>7}{'Est. savings/month':>22}",
    ]
    for _, title, items, total in report.by_check():
        lines.append(f"{title:<38}{len(items):>7}{usd(total):>22}")
    lines.append(f"{'Total':<38}{len(report.findings):>7}{usd(report.total_savings):>22}")
    biggest = sorted(report.findings, key=lambda f: -f.monthly_savings)[:top]
    if biggest:
        lines += ["", "Biggest items:"]
        for f in biggest:
            label = f"{f.resource_id} ({f.name})" if f.name else f.resource_id
            lines.append(f"  {usd(f.monthly_savings):>12}  {label} [{f.region}] - {f.action}")
    for error in report.errors:
        lines.append(f"warning: {error}")
    lines += ["", "Prices are approximate on-demand list prices; see the README."]
    return "\n".join(lines)
