"""Command line: `python -m receipts batch sample/recibos.csv --out recibos/`."""

from __future__ import annotations

import argparse
import os
import sys
from decimal import InvalidOperation
from pathlib import Path

from . import __version__
from .batch import decode, read_csv
from .extenso import reais_por_extenso
from .money import format_brl, parse_brl
from .pdf import render


def issuer_defaults(args: argparse.Namespace) -> dict[str, str]:
    """Issuer data from the command line, falling back to environment variables (same as the web app)."""
    return {
        "emitente": args.issuer or os.environ.get("ISSUER_NAME", ""),
        "documento_emitente": args.issuer_document or os.environ.get("ISSUER_DOCUMENT", ""),
        "cidade": args.city or os.environ.get("ISSUER_CITY", ""),
    }


def cmd_batch(args: argparse.Namespace) -> int:
    result = read_csv(decode(args.csv.read_bytes()), issuer_defaults(args))
    for line, message in result.errors:
        print(f"{args.csv}:{line}: {message}", file=sys.stderr)
    if not result.receipts:
        print("no valid receipts in the file", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    if args.single:
        target = args.out / args.single
        target.write_bytes(render(result.receipts))
        print(f"{target} ({len(result.receipts)} pages)")
    else:
        for receipt in result.receipts:
            target = args.out / receipt.filename
            target.write_bytes(render([receipt]))
            print(f"{target}  {receipt.amount_brl}  {receipt.payer}")
    total = sum(r.amount for r in result.receipts)
    print(f"{len(result.receipts)} receipts, total {format_brl(total)}; {len(result.errors)} rows with errors")
    return 2 if result.errors else 0


def cmd_words(args: argparse.Namespace) -> int:
    try:
        print(reais_por_extenso(parse_brl(args.amount)))
    except (ValueError, InvalidOperation) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="receipts", description="Brazilian payment receipts (recibos) as PDF.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    batch = sub.add_parser("batch", help="one PDF per CSV row (or a single PDF with --single)")
    batch.add_argument("csv", type=Path)
    batch.add_argument("--out", type=Path, default=Path("recibos"), help="output folder (default: recibos)")
    batch.add_argument("--single", metavar="NAME.pdf", help="write every receipt into one PDF instead")
    batch.add_argument("--issuer", help="issuer name when the CSV has no 'emitente' column (env ISSUER_NAME)")
    batch.add_argument("--issuer-document", help="issuer CPF/CNPJ (env ISSUER_DOCUMENT)")
    batch.add_argument("--city", help="city printed next to the date (env ISSUER_CITY)")
    batch.set_defaults(func=cmd_batch)

    words = sub.add_parser("extenso", help="print an amount in words, e.g. 1.200,50")
    words.add_argument("amount")
    words.set_defaults(func=cmd_words)

    args = parser.parse_args(argv)
    return args.func(args)
