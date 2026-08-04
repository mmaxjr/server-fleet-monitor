from pathlib import Path

import pytest

from fleet_monitor.app import main, parse_args


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
