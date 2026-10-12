"""Command line entry point: `costcheck --region us-east-1 --html report.html`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from . import __version__
from .checks import Options, scan
from .report import to_html, to_json, to_text


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="costcheck",
        description="Read-only scan of an AWS account for resources that cost money without doing work.",
    )
    p.add_argument("--profile", help="AWS profile name (default: the usual credential chain)")
    p.add_argument("--region", action="append", dest="regions", metavar="REGION", help="repeat for several regions")
    p.add_argument("--all-regions", action="store_true", help="scan every region enabled in the account")
    p.add_argument("--snapshot-age-days", type=int, default=90, help="report snapshots older than this (default 90)")
    p.add_argument("--stopped-days", type=int, default=7, help="report instances stopped for this long (default 7)")
    p.add_argument("--html", type=Path, default=Path("cost-report.html"), help="HTML report path")
    p.add_argument("--json", type=Path, help="also write the findings as JSON")
    p.add_argument("--no-html", action="store_true", help="do not write the HTML report")
    p.add_argument(
        "--fail-over",
        type=float,
        metavar="USD",
        help="exit with status 2 when estimated monthly savings exceed this value (for scheduled jobs and CI)",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p.parse_args(argv)


def resolve_regions(session, args: argparse.Namespace) -> list[str]:
    if args.all_regions:
        ec2 = session.client("ec2", region_name=session.region_name or "us-east-1")
        return sorted(r["RegionName"] for r in ec2.describe_regions()["Regions"])
    return args.regions or [session.region_name or "us-east-1"]


def main(argv: list[str] | None = None, session=None) -> int:
    args = parse_args(argv)
    try:
        session = session or boto3.Session(profile_name=args.profile)
        regions = resolve_regions(session, args)
        report = scan(session, regions, Options(args.snapshot_age_days, args.stopped_days))
    except NoCredentialsError:
        print("error: no AWS credentials found (configure a profile or environment variables)", file=sys.stderr)
        return 1
    except (BotoCoreError, ClientError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(to_text(report))
    if not args.no_html:
        args.html.write_text(to_html(report), encoding="utf-8")
        print(f"\nHTML report: {args.html}")
    if args.json:
        args.json.write_text(to_json(report), encoding="utf-8")
        print(f"JSON report: {args.json}")
    if args.fail_over is not None and report.total_savings > args.fail_over:
        return 2
    return 0
