from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer, Header, Input, Static

from .models import Inventory, Metrics, ServerSnapshot, ServerStatus
from .inventory import load_inventory
from .service import FleetService


def format_percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def format_uptime(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    days, remainder = divmod(int(seconds), 86400)
    hours = remainder // 3600
    return f"{days}d {hours}h" if days else f"{hours}h"


def primary_disk(metrics: Metrics | None) -> float | None:
    if not metrics or not metrics.disks:
        return None
    root = next((disk for disk in metrics.disks if disk.mountpoint == "/"), metrics.disks[0])
    return root.percent


class FleetMonitorApp(App[None]):
    TITLE = "Server Fleet Monitor"
    SUB_TITLE = "Debian via SSH"
    BINDINGS = [
        ("r", "refresh", "Atualizar"),
        ("/", "focus_filter", "Filtrar"),
        ("q", "quit", "Sair"),
    ]
    CSS = """
    Screen { layout: vertical; }
    #filter { height: 3; margin: 0 1; }
    #servers { height: 2fr; margin: 0 1; }
    #details { height: 1fr; min-height: 8; margin: 0 1 1 1; padding: 1 2;
               border: round $primary; overflow-y: auto; }
    """

    def __init__(self, inventory: Inventory, service: Any | None = None) -> None:
        super().__init__()
        self.inventory = inventory
        self.service = service or FleetService(inventory.settings)
        self.snapshots: dict[str, ServerSnapshot] = {}
        self._refresh_task: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(id="filter", placeholder="Filtrar por nome, IP ou estado")
        yield DataTable(id="servers", cursor_type="row", zebra_stripes=True)
        yield Static("Aguardando a primeira coleta…", id="details")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#servers", DataTable)
        table.add_columns("Servidor", "IP", "Estado", "CPU", "RAM", "Disco", "Load", "Coleta")
        await self.refresh_data()
        self.set_interval(self.inventory.settings.refresh_interval, self.action_refresh)

    async def refresh_data(self) -> None:
        self.snapshots = await self.service.refresh(self.inventory.servers)
        self._render_table(self.query_one("#filter", Input).value)
        if self.inventory.servers:
            self.show_details(self.inventory.servers[0].name)

    def action_refresh(self) -> None:
        if self._refresh_task and not self._refresh_task.done():
            return
        self._refresh_task = asyncio.create_task(self.refresh_data())

    def action_focus_filter(self) -> None:
        self.query_one("#filter", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._render_table(event.value)

    def _render_table(self, query: str = "") -> None:
        table = self.query_one("#servers", DataTable)
        table.clear()
        needle = query.casefold().strip()
        for server in self.inventory.servers:
            snapshot = self.snapshots.get(server.name)
            status = snapshot.status.value if snapshot else ServerStatus.COLLECTING.value
            if needle and needle not in f"{server.name} {server.host} {status}".casefold():
                continue
            metrics = snapshot.metrics if snapshot else None
            load = "—" if not metrics or not metrics.load_average else f"{metrics.load_average[0]:.2f}"
            table.add_row(
                server.name,
                server.host,
                status,
                format_percent(metrics.cpu_percent if metrics else None),
                format_percent(metrics.memory_percent if metrics else None),
                format_percent(primary_disk(metrics)),
                load,
                metrics.method if metrics else "—",
                key=server.name,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.show_details(str(event.row_key.value))

    def show_details(self, server_name: str) -> None:
        snapshot = self.snapshots.get(server_name)
        server = next((item for item in self.inventory.servers if item.name == server_name), None)
        if not server:
            return
        if not snapshot:
            body = f"[b]{escape(server.name)}[/b] ({escape(server.host)})\nColetando…"
        else:
            metrics = snapshot.metrics
            collected = snapshot.collected_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC") if snapshot.collected_at else "—"
            lines = [
                f"[b]{escape(server.name)}[/b] ({escape(server.host)})",
                f"Estado: {snapshot.status.value}  |  Última coleta: {collected}",
            ]
            if snapshot.error:
                lines.append(f"[red]Erro: {escape(snapshot.error)}[/red]")
            if metrics:
                lines.extend([
                    f"Método: {metrics.method}  |  Uptime: {format_uptime(metrics.uptime_seconds)}",
                    f"CPU: {format_percent(metrics.cpu_percent)}  |  RAM: {format_percent(metrics.memory_percent)}  |  Swap: {format_percent(metrics.swap_percent)}",
                    "Discos: " + (", ".join(f"{escape(d.mountpoint)} {format_percent(d.percent)}" for d in metrics.disks) or "—"),
                    "Serviços falhos: " + (", ".join(map(escape, metrics.failed_services)) or "nenhum"),
                    "Portas: " + (", ".join(map(escape, metrics.listening_ports[:20])) or "—"),
                    "Processos: " + (", ".join(f"{escape(p.name)}({p.pid})" for p in metrics.processes[:5]) or "—"),
                ])
            body = "\n".join(lines)
        self.query_one("#details", Static).update(body)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="fleet-monitor",
        description="Monitora múltiplos servidores Debian por SSH em uma interface de terminal.",
    )
    parser.add_argument(
        "--inventory",
        required=True,
        type=Path,
        help="caminho para o inventário YAML",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        inventory = load_inventory(args.inventory)
    except Exception as exc:
        print(f"Erro ao carregar inventário: {exc}", file=sys.stderr)
        return 2
    FleetMonitorApp(inventory).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
