"""Generate a sample report without an AWS account: builds a fake account with moto, then runs the CLI.

Usage (needs requirements-dev.txt): python scripts/demo_report.py [--html demo-report.html]
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ.update(
    AWS_ACCESS_KEY_ID="demo",
    AWS_SECRET_ACCESS_KEY="demo",
    AWS_DEFAULT_REGION="sa-east-1",
    MOTO_EC2_LOAD_DEFAULT_AMIS="false",
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402
from moto.core import DEFAULT_ACCOUNT_ID  # noqa: E402
from moto.ec2.models import ec2_backends  # noqa: E402

from costcheck.cli import main  # noqa: E402

NOW = datetime.now(UTC)


def ago(days: int) -> str:
    return (NOW - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def tags(kind: str, name: str) -> list[dict]:
    return [{"ResourceType": kind, "Tags": [{"Key": "Name", "Value": name}]}]


def build(session: boto3.Session) -> None:
    for region, spec in ACCOUNT.items():
        ec2 = session.client("ec2", region_name=region)
        backend = ec2_backends[DEFAULT_ACCOUNT_ID][region]
        zone = f"{region}a"

        for name, size, kind, days in spec["volumes"]:
            iops = {"Iops": 1000} if kind in ("io1", "io2") else {}
            vol = ec2.create_volume(
                AvailabilityZone=zone, Size=size, VolumeType=kind, TagSpecifications=tags("volume", name), **iops
            )
            backend.volumes[vol["VolumeId"]].create_time = ago(days)

        for name, size, days in spec["snapshots"]:
            source = ec2.create_volume(AvailabilityZone=zone, Size=size, VolumeType="gp3")["VolumeId"]
            snap = ec2.create_snapshot(VolumeId=source, Description=name, TagSpecifications=tags("snapshot", name))
            backend.snapshots[snap["SnapshotId"]].start_time = ago(days)
            ec2.delete_volume(VolumeId=source)

        for name, itype, extra_gb, stopped_days in spec["instances"]:
            iid = ec2.run_instances(
                ImageId="ami-0a1b2c3d",
                MinCount=1,
                MaxCount=1,
                InstanceType=itype,
                TagSpecifications=tags("instance", name),
            )["Instances"][0]["InstanceId"]
            if extra_gb:
                vol = ec2.create_volume(AvailabilityZone=zone, Size=extra_gb, VolumeType="gp2")["VolumeId"]
                ec2.attach_volume(VolumeId=vol, InstanceId=iid, Device="/dev/sdf")
            if stopped_days is not None:
                ec2.stop_instances(InstanceIds=[iid])
                stamp = (NOW - timedelta(days=stopped_days)).strftime("%Y-%m-%d %H:%M:%S UTC")
                backend.get_instance(iid)._reason = f"User initiated ({stamp})"

        for name in spec["idle_ips"]:
            ec2.allocate_address(Domain="vpc", TagSpecifications=tags("elastic-ip", name))


# A small Brazilian e-commerce company: production in São Paulo, a few leftovers in N. Virginia.
ACCOUNT = {
    "sa-east-1": {
        "volumes": [
            ("erp-db-antigo", 500, "gp2", 212),
            ("sftp-notas-fiscais", 200, "gp2", 145),
            ("teste-migracao-pg", 100, "io1", 61),
        ],
        "snapshots": [
            ("backup-financeiro-2024", 500, 410),
            ("pre-upgrade-erp", 250, 302),
            ("loja-virtual-ami-base", 80, 188),
            ("backup-diario", 120, 3),
        ],
        "instances": [
            ("erp-homologacao", "m6i.xlarge", 300, 64),
            ("bi-metabase-antigo", "t3.large", 150, 120),
            ("loja-virtual-web-1", "m4.xlarge", 0, None),
            ("loja-virtual-web-2", "m4.xlarge", 0, None),
            ("fila-pedidos", "c4.large", 0, None),
            ("api-frete", "t3.medium", 0, None),
        ],
        "idle_ips": ["vpn-escritorio-antigo", "ftp-legado"],
    },
    "us-east-1": {
        "volumes": [("poc-data-lake", 1000, "st1", 96)],
        "snapshots": [("poc-data-lake-final", 1000, 95)],
        "instances": [("poc-jupyter", "r4.large", 200, 97), ("cdn-origin", "t2.medium", 0, None)],
        "idle_ips": ["poc-nat"],
    },
}


if __name__ == "__main__":
    with mock_aws():
        session = boto3.Session(region_name="sa-east-1")
        build(session)
        args = sys.argv[1:] or ["--html", "demo-report.html"]
        sys.exit(main(["--region", "sa-east-1", "--region", "us-east-1", *args], session=session))
