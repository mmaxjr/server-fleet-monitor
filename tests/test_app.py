from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from textual.widgets import DataTable, Static

from fleet_monitor.app import FleetMonitorApp, format_percent
from fleet_monitor.models import (
    DiskMetric,
    Inventory,
    Metrics,
    ServerConfig,
    ServerSnapshot,
    ServerStatus,
    Settings,
)


SERVERS = [
    ServerConfig(name="web", host="10.0.0.2", username="ops", password=SecretStr("secret")),
    ServerConfig(name="db", host="10.0.0.3", username="ops", password=SecretStr("secret2")),
]
SNAPSHOTS = {
    "web": ServerSnapshot(
        server_name="web",
        status=ServerStatus.ONLINE,
        collected_at=datetime.now(UTC),
        metrics=Metrics(
            method="psutil",
            cpu_percent=20,
            memory_percent=40,
            load_average=(0.1, 0.2, 0.3),
            uptime_seconds=3600,
            disks=[DiskMetric(mountpoint="/", percent=61)],
        ),
    ),
    "db": ServerSnapshot(server_name="db", status=ServerStatus.OFFLINE, error="timeout"),
}


class FakeFleetService:
    async def refresh(self, servers: list[ServerConfig]) -> dict[str, ServerSnapshot]:
        return SNAPSHOTS


def test_format_percent_handles_missing_values() -> None:
    assert format_percent(None) == "—"
    assert format_percent(12.34) == "12.3%"


@pytest.mark.asyncio
async def test_dashboard_lists_servers_without_password() -> None:
    inventory = Inventory(settings=Settings(refresh_interval=3600), servers=SERVERS)
    app = FleetMonitorApp(inventory, service=FakeFleetService())

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#servers", DataTable)
        assert table.row_count == 2
        rendered_rows = " ".join(str(value) for row in range(2) for value in table.get_row_at(row))
        assert "web" in rendered_rows
        assert "offline" in rendered_rows.lower()
        assert "secret" not in rendered_rows


@pytest.mark.asyncio
async def test_selecting_server_updates_details() -> None:
    inventory = Inventory(settings=Settings(refresh_interval=3600), servers=SERVERS)
    app = FleetMonitorApp(inventory, service=FakeFleetService())

    async with app.run_test() as pilot:
        await pilot.pause()
        app.show_details("web")
        await pilot.pause()
        details = app.query_one("#details", Static)
        assert "psutil" in str(details.render())
        assert "61.0%" in str(details.render())

