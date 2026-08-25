from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import ServerSnapshot

CSV_FIELDS = [
    "server_name",
    "status",
    "collected_at",
    "method",
    "cpu_percent",
    "memory_percent",
    "swap_percent",
    "load_average",
    "uptime_seconds",
    "disks",
    "failed_services",
    "listening_ports",
    "error",
]


def export_json(snapshots: dict[str, ServerSnapshot], path: Path) -> None:
    payload = [snapshot.model_dump(mode="json") for snapshot in snapshots.values()]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def export_csv(snapshots: dict[str, ServerSnapshot], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for snapshot in snapshots.values():
            metrics = snapshot.metrics
            writer.writerow(
                {
                    "server_name": snapshot.server_name,
                    "status": snapshot.status.value,
                    "collected_at": snapshot.collected_at.isoformat() if snapshot.collected_at else "",
                    "method": metrics.method if metrics else "",
                    "cpu_percent": metrics.cpu_percent if metrics else "",
                    "memory_percent": metrics.memory_percent if metrics else "",
                    "swap_percent": metrics.swap_percent if metrics else "",
                    "load_average": ",".join(f"{v:.2f}" for v in metrics.load_average) if metrics and metrics.load_average else "",
                    "uptime_seconds": metrics.uptime_seconds if metrics else "",
                    "disks": ";".join(f"{d.mountpoint}:{d.percent}" for d in metrics.disks) if metrics else "",
                    "failed_services": ";".join(metrics.failed_services) if metrics else "",
                    "listening_ports": ";".join(metrics.listening_ports) if metrics else "",
                    "error": snapshot.error or "",
                }
            )
