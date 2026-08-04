from __future__ import annotations

import os
import warnings
from pathlib import Path

import yaml

from .models import Inventory


def warn_if_insecure_permissions(path: Path) -> None:
    if os.name != "posix":
        return
    if path.stat().st_mode & 0o077:
        warnings.warn(
            f"{path} contém credenciais e deveria usar permissão 0600",
            UserWarning,
            stacklevel=2,
        )


def load_inventory(path: Path) -> Inventory:
    if not path.is_file():
        raise FileNotFoundError(f"inventário não encontrado: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    inventory = Inventory.model_validate(payload)
    names = [server.name for server in inventory.servers]
    if len(names) != len(set(names)):
        raise ValueError("inventário contém nomes duplicados")
    warn_if_insecure_permissions(path)
    return inventory

