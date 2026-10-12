"""Approximate on-demand prices in USD (us-east-1, Linux), used to estimate monthly savings.

These are list prices rounded from the public AWS price pages. Other regions are usually a bit more
expensive, discounts (Savings Plans, Reserved Instances, credits) are ignored, and prices change over
time: treat every number in the report as an order of magnitude, not a quote.
"""

from __future__ import annotations

HOURS_PER_MONTH = 730

# USD per GB-month of provisioned storage.
EBS_GB_MONTH = {
    "gp3": 0.08,
    "gp2": 0.10,
    "io1": 0.125,
    "io2": 0.125,
    "st1": 0.045,
    "sc1": 0.015,
    "standard": 0.05,
}
EBS_IOPS_MONTH = {"io1": 0.065, "io2": 0.065, "gp3": 0.005}  # per provisioned IOPS (gp3: above 3000)
GP3_FREE_IOPS = 3000
SNAPSHOT_GB_MONTH = 0.05
# Public IPv4 address that is allocated but not associated: USD 0.005 per hour.
IDLE_IPV4_MONTH = 0.005 * HOURS_PER_MONTH

# USD per hour, on-demand Linux.
INSTANCE_HOUR = {
    "t2.micro": 0.0116,
    "t2.small": 0.023,
    "t2.medium": 0.0464,
    "t2.large": 0.0928,
    "t2.xlarge": 0.1856,
    "t3.micro": 0.0104,
    "t3.small": 0.0208,
    "t3.medium": 0.0416,
    "t3.large": 0.0832,
    "t3.xlarge": 0.1664,
    "m4.large": 0.10,
    "m4.xlarge": 0.20,
    "m4.2xlarge": 0.40,
    "m6i.large": 0.096,
    "m6i.xlarge": 0.192,
    "m6i.2xlarge": 0.384,
    "c4.large": 0.10,
    "c4.xlarge": 0.199,
    "c4.2xlarge": 0.398,
    "c6i.large": 0.085,
    "c6i.xlarge": 0.17,
    "c6i.2xlarge": 0.34,
    "r4.large": 0.133,
    "r4.xlarge": 0.266,
    "r4.2xlarge": 0.532,
    "r6i.large": 0.126,
    "r6i.xlarge": 0.252,
    "r6i.2xlarge": 0.504,
    "m3.large": 0.133,
    "c3.large": 0.105,
    "r3.large": 0.166,
}

# Previous-generation family -> current family with the same size names.
SUCCESSOR_FAMILY = {
    "t1": "t3",
    "t2": "t3",
    "m1": "m6i",
    "m3": "m6i",
    "m4": "m6i",
    "c1": "c6i",
    "c3": "c6i",
    "c4": "c6i",
    "r3": "r6i",
    "r4": "r6i",
    "i2": "i4i",
    "d2": "d3",
}


def volume_month(volume_type: str, size_gb: int, iops: int | None = None) -> float:
    """Monthly cost of an EBS volume: storage plus provisioned IOPS where they are billed."""
    cost = size_gb * EBS_GB_MONTH.get(volume_type, EBS_GB_MONTH["gp2"])
    if volume_type in ("io1", "io2") and iops:
        cost += iops * EBS_IOPS_MONTH[volume_type]
    elif volume_type == "gp3" and iops and iops > GP3_FREE_IOPS:
        cost += (iops - GP3_FREE_IOPS) * EBS_IOPS_MONTH["gp3"]
    return round(cost, 2)


def snapshot_month(size_gb: int) -> float:
    """Upper bound: snapshots are incremental, so the billed size is usually smaller than the volume."""
    return round(size_gb * SNAPSHOT_GB_MONTH, 2)


def instance_month(instance_type: str) -> float | None:
    hourly = INSTANCE_HOUR.get(instance_type)
    return None if hourly is None else round(hourly * HOURS_PER_MONTH, 2)


def successor(instance_type: str) -> str | None:
    """'m4.large' -> 'm6i.large'; None when the family is current."""
    family, _, size = instance_type.partition(".")
    new_family = SUCCESSOR_FAMILY.get(family)
    return f"{new_family}.{size}" if new_family else None
