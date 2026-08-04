from pathlib import Path

import pytest

from fleet_monitor.inventory import load_inventory


def write_inventory(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "inventory.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_inventory_applies_defaults_and_hides_password(tmp_path: Path) -> None:
    path = write_inventory(
        tmp_path,
        "servers:\n"
        "  - name: web\n"
        "    host: 10.0.0.2\n"
        "    username: ops\n"
        "    password: secret\n",
    )

    inventory = load_inventory(path)

    assert inventory.servers[0].port == 22
    assert inventory.settings.refresh_interval == 10
    assert inventory.settings.ssh_timeout == 5
    assert "secret" not in repr(inventory)


def test_duplicate_names_are_rejected(tmp_path: Path) -> None:
    path = write_inventory(
        tmp_path,
        "servers:\n"
        "  - {name: web, host: 10.0.0.2, username: ops, password: one}\n"
        "  - {name: web, host: 10.0.0.3, username: ops, password: two}\n",
    )

    with pytest.raises(ValueError, match="nomes duplicados"):
        load_inventory(path)


def test_invalid_threshold_order_is_rejected(tmp_path: Path) -> None:
    path = write_inventory(
        tmp_path,
        "settings: {warning_threshold: 95, critical_threshold: 90}\n"
        "servers:\n"
        "  - {name: web, host: 10.0.0.2, username: ops, password: one}\n",
    )

    with pytest.raises(ValueError, match="warning_threshold"):
        load_inventory(path)

