import json
import subprocess
import sys
from pathlib import Path

from costcheck.checks import scan
from costcheck.cli import main
from costcheck.report import to_html, to_text
from tests.conftest import name_tag, run


def test_cli_writes_html_and_json(session, ec2, tmp_path, capsys):
    ec2.create_volume(AvailabilityZone="us-east-1a", Size=500, VolumeType="st1")
    ec2.allocate_address(Domain="vpc")
    html, js = tmp_path / "r.html", tmp_path / "r.json"

    assert main(["--region", "us-east-1", "--html", str(html), "--json", str(js)], session=session) == 0

    out = capsys.readouterr().out
    assert "Unattached EBS volumes" in out and "US$ 26.15" in out  # 22.50 + 3.65
    page = html.read_text()
    assert "<style>" in page and "https://" not in page  # self-contained
    assert "US$ 26.15" in page and "US$ 313.80" in page  # monthly and yearly
    data = json.loads(js.read_text())
    assert data["total_monthly_savings"] == 26.15 and len(data["findings"]) == 2


def test_fail_over_threshold(session, ec2, tmp_path):
    ec2.allocate_address(Domain="vpc")
    args = ["--no-html", "--region", "us-east-1"]
    assert main([*args, "--fail-over", "1"], session=session) == 2
    assert main([*args, "--fail-over", "100"], session=session) == 0


def test_all_regions(session, capsys):
    assert main(["--all-regions", "--no-html"], session=session) == 0
    assert "sa-east-1" in capsys.readouterr().out


def test_html_escapes_resource_names(session, ec2):
    ec2.create_volume(
        AvailabilityZone="us-east-1a", Size=1, VolumeType="gp2", TagSpecifications=name_tag("volume", "<b>x</b>")
    )
    run(ec2)
    page = to_html(scan(session, ["us-east-1"]))
    assert "&lt;b&gt;x&lt;/b&gt;" in page and "<b>x</b>" not in page


def test_text_summary_lists_biggest_items(session, ec2):
    ec2.create_volume(
        AvailabilityZone="us-east-1a", Size=300, VolumeType="gp2", TagSpecifications=name_tag("volume", "erp-db")
    )
    text = to_text(scan(session, ["us-east-1"]))
    assert "Total" in text and "US$ 30.00" in text
    assert "(erp-db) [us-east-1]" in text


def test_no_credentials_is_a_clear_error(monkeypatch, capsys):
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(var)
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", "/nonexistent")
    monkeypatch.setenv("AWS_CONFIG_FILE", "/nonexistent")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    assert main(["--no-html", "--region", "us-east-1"]) == 1
    assert "no AWS credentials" in capsys.readouterr().err


def test_demo_script(tmp_path):
    script = Path(__file__).parent.parent / "scripts" / "demo_report.py"
    out = tmp_path / "demo.html"
    result = subprocess.run([sys.executable, str(script), "--html", str(out)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "erp-homologacao" in out.read_text()
