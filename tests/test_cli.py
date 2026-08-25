from pathlib import Path

import pytest

from fleet_monitor.app import main, parse_args
from fleet_monitor.models import Metrics, ServerSnapshot, ServerStatus


def test_cli_requires_inventory() -> None:
    with pytest.raises(SystemExit) as error:
        parse_args([])
    assert error.value.code == 2


def test_cli_accepts_inventory_path() -> None:
    args = parse_args(["--inventory", "/etc/fleet/inventory.yaml"])
    assert args.inventory == Path("/etc/fleet/inventory.yaml")


def test_main_loads_inventory_and_runs_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text(
        "servers:\n  - {name: web, host: 10.0.0.2, username: ops, password: secret}\n",
        encoding="utf-8",
    )
    calls: list[str] = []

    class DummyApp:
        def __init__(self, loaded: object) -> None:
            calls.append("created")

        def run(self) -> None:
            calls.append("run")

    monkeypatch.setattr("fleet_monitor.app.FleetMonitorApp", DummyApp)

    assert main(["--inventory", str(inventory)]) == 0
    assert calls == ["created", "run"]


def test_main_export_writes_file_and_skips_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text(
        "servers:\n  - {name: web, host: 10.0.0.2, username: ops, password: secret}\n",
        encoding="utf-8",
    )
    export_path = tmp_path / "out.json"

    class DummyApp:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("dashboard should not start in export mode")

    class DummyService:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def refresh(self, servers: list[object]) -> dict[str, ServerSnapshot]:
            return {
                "web": ServerSnapshot(
                    server_name="web",
                    status=ServerStatus.ONLINE,
                    metrics=Metrics(method="fallback", cpu_percent=1.0),
                )
            }

    monkeypatch.setattr("fleet_monitor.app.FleetMonitorApp", DummyApp)
    monkeypatch.setattr("fleet_monitor.app.FleetService", DummyService)

    code = main(["--inventory", str(inventory), "--export", "json", "--export-path", str(export_path)])

    assert code == 0
    assert export_path.exists()
    assert "web" in export_path.read_text(encoding="utf-8")
