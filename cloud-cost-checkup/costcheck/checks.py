"""The checks. Each one reads a region with an EC2 client and returns findings; nothing is modified."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from . import prices

CHECKS = {
    "unattached_volumes": "Unattached EBS volumes",
    "old_snapshots": "Old EBS snapshots",
    "stopped_instances": "Stopped instances with volumes",
    "idle_elastic_ips": "Unassociated Elastic IPs",
    "old_generation": "Previous-generation instance types",
}
STOPPED_AT = re.compile(r"\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


@dataclass(frozen=True)
class Options:
    snapshot_age_days: int = 90
    stopped_days: int = 7


@dataclass
class Finding:
    check: str
    region: str
    resource_id: str
    name: str
    detail: str
    action: str
    monthly_savings: float
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Report:
    account_id: str
    regions: list[str]
    generated_at: datetime
    options: Options
    findings: list[Finding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_savings(self) -> float:
        return round(sum(f.monthly_savings for f in self.findings), 2)

    def by_check(self) -> list[tuple[str, str, list[Finding], float]]:
        """(key, title, findings sorted by savings, subtotal) for every check, in a fixed order."""
        rows = []
        for key, title in CHECKS.items():
            items = sorted((f for f in self.findings if f.check == key), key=lambda f: -f.monthly_savings)
            rows.append((key, title, items, round(sum(f.monthly_savings for f in items), 2)))
        return rows

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "regions": self.regions,
            "generated_at": self.generated_at.isoformat(timespec="seconds"),
            "options": asdict(self.options),
            "currency": "USD",
            "total_monthly_savings": self.total_savings,
            "summary": {
                key: {"count": len(items), "monthly_savings": total} for key, _, items, total in self.by_check()
            },
            "findings": [f.to_dict() for f in self.findings],
            "errors": self.errors,
        }


def tag_name(tags: list[dict] | None) -> str:
    return next((t["Value"] for t in tags or [] if t.get("Key") == "Name"), "")


def as_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _paginate(client, operation: str, key: str, **kwargs):
    for page in client.get_paginator(operation).paginate(**kwargs):
        yield from page.get(key, [])


def unattached_volumes(ec2, region: str, now: datetime, opts: Options) -> list[Finding]:
    findings = []
    for v in _paginate(ec2, "describe_volumes", "Volumes", Filters=[{"Name": "status", "Values": ["available"]}]):
        cost = prices.volume_month(v["VolumeType"], v["Size"], v.get("Iops"))
        age = (now - as_utc(v["CreateTime"])).days
        findings.append(
            Finding(
                check="unattached_volumes",
                region=region,
                resource_id=v["VolumeId"],
                name=tag_name(v.get("Tags")),
                detail=f"{v['Size']} GB {v['VolumeType']}, not attached to any instance, created {age} days ago",
                action="Snapshot it if the data matters, then delete the volume",
                monthly_savings=cost,
                data={"size_gb": v["Size"], "type": v["VolumeType"], "age_days": age},
            )
        )
    return findings


def old_snapshots(ec2, region: str, now: datetime, opts: Options) -> list[Finding]:
    # Snapshots behind a registered AMI cannot be deleted without deregistering the image first: skip them.
    images = ec2.describe_images(Owners=["self"]).get("Images", [])
    in_use = {m["Ebs"]["SnapshotId"] for img in images for m in img.get("BlockDeviceMappings", []) if "Ebs" in m} - {
        None
    }
    limit = now - timedelta(days=opts.snapshot_age_days)
    findings = []
    for s in _paginate(ec2, "describe_snapshots", "Snapshots", OwnerIds=["self"]):
        started = as_utc(s["StartTime"])
        if started > limit or s["SnapshotId"] in in_use:
            continue
        age = (now - started).days
        findings.append(
            Finding(
                check="old_snapshots",
                region=region,
                resource_id=s["SnapshotId"],
                name=tag_name(s.get("Tags")) or s.get("Description", "")[:60],
                detail=f"{s['VolumeSize']} GB, {age} days old",
                action="Delete it, or move it to the archive tier if it must be kept",
                monthly_savings=prices.snapshot_month(s["VolumeSize"]),
                data={"size_gb": s["VolumeSize"], "age_days": age, "volume_id": s.get("VolumeId")},
            )
        )
    return findings


def _instances(ec2, state: str):
    for reservation in _paginate(
        ec2, "describe_instances", "Reservations", Filters=[{"Name": "instance-state-name", "Values": [state]}]
    ):
        yield from reservation["Instances"]


def stopped_instances(ec2, region: str, now: datetime, opts: Options) -> list[Finding]:
    findings = []
    for inst in _instances(ec2, "stopped"):
        match = STOPPED_AT.search(inst.get("StateTransitionReason", ""))
        stopped_days = (now - datetime.fromisoformat(match.group(1)).replace(tzinfo=UTC)).days if match else None
        if stopped_days is not None and stopped_days < opts.stopped_days:
            continue
        volume_ids = [m["Ebs"]["VolumeId"] for m in inst.get("BlockDeviceMappings", []) if "Ebs" in m]
        if not volume_ids:
            continue
        volumes = ec2.describe_volumes(VolumeIds=volume_ids)["Volumes"]
        cost = round(sum(prices.volume_month(v["VolumeType"], v["Size"], v.get("Iops")) for v in volumes), 2)
        total_gb = sum(v["Size"] for v in volumes)
        since = f"stopped {stopped_days} days ago" if stopped_days is not None else "stopped"
        findings.append(
            Finding(
                check="stopped_instances",
                region=region,
                resource_id=inst["InstanceId"],
                name=tag_name(inst.get("Tags")),
                detail=f"{inst['InstanceType']}, {since}, {len(volumes)} volume(s) / {total_gb} GB still billed",
                action="Create an AMI or snapshot, then terminate the instance",
                monthly_savings=cost,
                data={"instance_type": inst["InstanceType"], "stopped_days": stopped_days, "volume_gb": total_gb},
            )
        )
    return findings


def idle_elastic_ips(ec2, region: str, now: datetime, opts: Options) -> list[Finding]:
    findings = []
    for a in ec2.describe_addresses().get("Addresses", []):
        if a.get("AssociationId") or a.get("InstanceId") or a.get("NetworkInterfaceId"):
            continue
        findings.append(
            Finding(
                check="idle_elastic_ips",
                region=region,
                resource_id=a.get("AllocationId", a["PublicIp"]),
                name=tag_name(a.get("Tags")),
                detail=f"{a['PublicIp']} is allocated but not associated",
                action="Release the address if nothing depends on it",
                monthly_savings=round(prices.IDLE_IPV4_MONTH, 2),
                data={"public_ip": a["PublicIp"]},
            )
        )
    return findings


def old_generation(ec2, region: str, now: datetime, opts: Options) -> list[Finding]:
    findings = []
    for inst in _instances(ec2, "running"):
        current = inst["InstanceType"]
        target = prices.successor(current)
        if not target:
            continue
        old_price, new_price = prices.instance_month(current), prices.instance_month(target)
        known = old_price is not None and new_price is not None
        savings = round(max(old_price - new_price, 0), 2) if known else 0.0
        price_note = f"US$ {old_price:.2f} -> US$ {new_price:.2f} per month" if known else "price not in the table"
        findings.append(
            Finding(
                check="old_generation",
                region=region,
                resource_id=inst["InstanceId"],
                name=tag_name(inst.get("Tags")),
                detail=f"{current} is a previous generation; {target} is faster ({price_note})",
                action=f"Change the instance type to {target} in the next maintenance window",
                monthly_savings=savings,
                data={"instance_type": current, "suggested_type": target},
            )
        )
    return findings


RUNNERS = {
    "unattached_volumes": unattached_volumes,
    "old_snapshots": old_snapshots,
    "stopped_instances": stopped_instances,
    "idle_elastic_ips": idle_elastic_ips,
    "old_generation": old_generation,
}


def scan(session, regions: list[str], opts: Options | None = None, now: datetime | None = None) -> Report:
    """Run every check in every region. Errors (e.g. a region without permission) are collected, not raised."""
    opts = opts or Options()
    now = now or datetime.now(UTC)
    try:
        account = session.client("sts").get_caller_identity()["Account"]
    except NoCredentialsError:
        raise
    except (BotoCoreError, ClientError):
        account = "unknown"
    report = Report(account_id=account, regions=regions, generated_at=now, options=opts)
    for region in regions:
        ec2 = session.client("ec2", region_name=region)
        for key, run in RUNNERS.items():
            try:
                report.findings.extend(run(ec2, region, now, opts))
            except (BotoCoreError, ClientError) as exc:
                report.errors.append(f"{region} / {CHECKS[key]}: {exc}")
    return report
