from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from fleet_monitor.export import export_csv, export_json
from fleet_monitor.models import DiskMetric, Metrics, ServerSnapshot, ServerStatus

SNAPSHOT = ServerSnapshot(
    server_name="web-01",
    status=ServerStatus.ONLINE,
    collected_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    metrics=Metrics(
        method="psutil",
        cpu_percent=12.5,
        memory_percent=45.0,
        load_average=(0.1, 0.2, 0.3),
        disks=[DiskMetric(mountpoint="/", percent=55.0)],
        failed_services=["nginx"],
        listening_ports=["22/tcp"],
    ),
)

OFFLINE_SNAPSHOT = ServerSnapshot(
    server_name="db-01",
    status=ServerStatus.OFFLINE,
    error="timeout",
)


def test_export_json_preserves_status_and_metrics(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"

    export_json({"web-01": SNAPSHOT, "db-01": OFFLINE_SNAPSHOT}, path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    by_name = {item["server_name"]: item for item in payload}
    assert by_name["web-01"]["status"] == "online"
    assert by_name["web-01"]["metrics"]["cpu_percent"] == 12.5
    assert by_name["db-01"]["status"] == "offline"
    assert by_name["db-01"]["error"] == "timeout"


def test_export_csv_is_spreadsheet_friendly(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.csv"

    export_csv({"web-01": SNAPSHOT, "db-01": OFFLINE_SNAPSHOT}, path)

    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    by_name = {row["server_name"]: row for row in rows}
    assert by_name["web-01"]["status"] == "online"
    assert by_name["web-01"]["cpu_percent"] == "12.5"
    assert by_name["web-01"]["disks"] == "/:55.0"
    assert by_name["web-01"]["failed_services"] == "nginx"
    assert by_name["db-01"]["status"] == "offline"
    assert by_name["db-01"]["error"] == "timeout"
