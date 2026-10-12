import pytest

from costcheck import prices


def test_volume_prices():
    assert prices.volume_month("gp2", 100) == 10.0
    assert prices.volume_month("gp3", 100, iops=3000) == 8.0
    assert prices.volume_month("gp3", 100, iops=4000) == 13.0  # 1000 extra IOPS
    assert prices.volume_month("io1", 50, iops=1000) == pytest.approx(71.25)
    assert prices.volume_month("unknown", 10) == 1.0  # falls back to gp2


def test_snapshot_and_ip():
    assert prices.snapshot_month(200) == 10.0
    assert prices.IDLE_IPV4_MONTH == pytest.approx(3.65)


def test_successor():
    assert prices.successor("m4.large") == "m6i.large"
    assert prices.successor("t2.micro") == "t3.micro"
    assert prices.successor("m6i.large") is None
    assert prices.instance_month("m4.large") == 73.0
    assert prices.instance_month("x9.huge") is None
