import os

# Fake credentials and no default AMIs (their snapshots would show up as "owned by self" in moto).
os.environ.update(
    AWS_ACCESS_KEY_ID="testing",
    AWS_SECRET_ACCESS_KEY="testing",
    AWS_SESSION_TOKEN="testing",
    AWS_DEFAULT_REGION="us-east-1",
    MOTO_EC2_LOAD_DEFAULT_AMIS="false",
)

import boto3  # noqa: E402
import pytest  # noqa: E402
from moto import mock_aws  # noqa: E402

AMI = "ami-12345678"


@pytest.fixture
def session():
    with mock_aws():
        yield boto3.Session(region_name="us-east-1")


@pytest.fixture
def ec2(session):
    return session.client("ec2")


def name_tag(kind: str, name: str) -> list[dict]:
    return [{"ResourceType": kind, "Tags": [{"Key": "Name", "Value": name}]}]


def run(ec2, instance_type="t3.micro", name=""):
    tags = name_tag("instance", name) if name else []
    return ec2.run_instances(ImageId=AMI, MinCount=1, MaxCount=1, InstanceType=instance_type, TagSpecifications=tags)[
        "Instances"
    ][0]["InstanceId"]
