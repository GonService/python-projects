from datetime import UTC, datetime, timedelta

from botocore.exceptions import ClientError

from costcheck import checks
from costcheck.checks import Options, scan
from tests.conftest import name_tag, run

LATER = datetime.now(UTC) + timedelta(days=120)


def found(report, check):
    return {f.resource_id: f for f in report.findings if f.check == check}


def test_unattached_volumes(session, ec2):
    loose = ec2.create_volume(
        AvailabilityZone="us-east-1a", Size=100, VolumeType="gp2", TagSpecifications=name_tag("volume", "old-backup")
    )["VolumeId"]
    attached = ec2.create_volume(AvailabilityZone="us-east-1a", Size=50, VolumeType="gp3")["VolumeId"]
    instance = run(ec2)
    ec2.attach_volume(VolumeId=attached, InstanceId=instance, Device="/dev/sdf")

    result = found(scan(session, ["us-east-1"]), "unattached_volumes")
    assert list(result) == [loose]
    assert result[loose].monthly_savings == 10.0 and result[loose].name == "old-backup"


def test_old_snapshots_skip_recent_and_ami_backed(session, ec2):
    volume = ec2.create_volume(AvailabilityZone="us-east-1a", Size=200, VolumeType="gp2")["VolumeId"]
    old = ec2.create_snapshot(VolumeId=volume, Description="nightly")["SnapshotId"]
    ec2.register_image(Name="golden", RootDeviceName="/dev/sda1")
    image = ec2.describe_images(Owners=["self"])["Images"][0]
    behind_ami = image["BlockDeviceMappings"][0]["Ebs"]["SnapshotId"]
    assert behind_ami in {s["SnapshotId"] for s in ec2.describe_snapshots(OwnerIds=["self"])["Snapshots"]}

    assert found(scan(session, ["us-east-1"]), "old_snapshots") == {}  # everything was created just now
    result = found(scan(session, ["us-east-1"], now=LATER), "old_snapshots")
    assert list(result) == [old]
    assert result[old].monthly_savings == 10.0 and result[old].data["age_days"] >= 119


def test_stopped_instances_report_their_volumes(session, ec2):
    stopped = run(ec2, "m6i.large", name="erp-homologacao")
    extra = ec2.create_volume(AvailabilityZone="us-east-1a", Size=92, VolumeType="gp2")["VolumeId"]
    ec2.attach_volume(VolumeId=extra, InstanceId=stopped, Device="/dev/sdf")
    run(ec2)  # running: not reported
    ec2.stop_instances(InstanceIds=[stopped])

    assert found(scan(session, ["us-east-1"]), "stopped_instances") == {}  # stopped less than 7 days ago
    result = found(scan(session, ["us-east-1"], now=LATER), "stopped_instances")
    assert list(result) == [stopped]
    finding = result[stopped]
    assert finding.monthly_savings == 10.0  # 8 GB root + 92 GB, gp2
    assert finding.name == "erp-homologacao" and "100 GB" in finding.detail
    assert found(scan(session, ["us-east-1"], Options(stopped_days=0)), "stopped_instances")


def test_idle_elastic_ips(session, ec2):
    idle = ec2.allocate_address(Domain="vpc")["AllocationId"]
    used = ec2.allocate_address(Domain="vpc")["AllocationId"]
    ec2.associate_address(AllocationId=used, InstanceId=run(ec2))

    result = found(scan(session, ["us-east-1"]), "idle_elastic_ips")
    assert list(result) == [idle]
    assert result[idle].monthly_savings == 3.65


def test_old_generation_instances(session, ec2):
    old = run(ec2, "m4.large")
    unknown_price = run(ec2, "m3.medium")
    run(ec2, "m6i.large")
    result = found(scan(session, ["us-east-1"]), "old_generation")
    assert set(result) == {old, unknown_price}
    assert result[old].monthly_savings == 2.92  # (0.100 - 0.096) * 730
    assert result[old].data["suggested_type"] == "m6i.large"
    assert result[unknown_price].monthly_savings == 0 and "not in the table" in result[unknown_price].detail


def test_several_regions_and_summary(session):
    for region in ("us-east-1", "sa-east-1"):
        session.client("ec2", region_name=region).allocate_address(Domain="vpc")
    report = scan(session, ["us-east-1", "sa-east-1"])
    assert report.account_id == "123456789012"
    assert {f.region for f in report.findings} == {"us-east-1", "sa-east-1"}
    assert report.total_savings == 7.3
    summary = report.to_dict()["summary"]
    assert summary["idle_elastic_ips"] == {"count": 2, "monthly_savings": 7.3}
    assert summary["old_snapshots"]["count"] == 0


def test_errors_are_collected_not_raised(session, monkeypatch):
    def denied(*_args):
        raise ClientError({"Error": {"Code": "UnauthorizedOperation", "Message": "denied"}}, "DescribeAddresses")

    monkeypatch.setitem(checks.RUNNERS, "idle_elastic_ips", denied)
    report = scan(session, ["us-east-1"])
    assert len(report.errors) == 1 and "Unassociated Elastic IPs" in report.errors[0]
