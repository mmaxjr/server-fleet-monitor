from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from .collector import CollectionError, HybridCollector
from .models import Metrics, ServerConfig, ServerSnapshot, ServerStatus, Settings
from .ssh import ParamikoExecutor, map_ssh_error


ExecutorFactory = Callable[[ServerConfig, float], Any]


class FleetService:
    def __init__(
        self,
        settings: Settings,
        collector: HybridCollector | Any | None = None,
        executor_factory: ExecutorFactory = ParamikoExecutor,
    ) -> None:
        self.settings = settings
        self.collector = collector or HybridCollector()
        self.executor_factory = executor_factory
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        self._snapshots: dict[str, ServerSnapshot] = {}

    def _collect_sync(self, server: ServerConfig) -> Metrics:
        executor = self.executor_factory(server, self.settings.ssh_timeout)
        try:
            return self.collector.collect(executor)
        finally:
            executor.close()

    async def _collect_one(self, server: ServerConfig) -> ServerSnapshot:
        async with self._semaphore:
            try:
                metrics = await asyncio.wait_for(
                    asyncio.to_thread(self._collect_sync, server),
                    timeout=self.settings.ssh_timeout + 2,
                )
                snapshot = ServerSnapshot(
                    server_name=server.name,
                    status=ServerStatus.ONLINE,
                    collected_at=datetime.now(UTC),
                    metrics=metrics,
                )
            except Exception as exc:
                password = server.password.get_secret_value()
                if isinstance(exc, CollectionError):
                    status, message = ServerStatus.COLLECTION_ERROR, str(exc).replace(password, "<redacted>")
                else:
                    status, message = map_ssh_error(exc, password)
                previous = self._snapshots.get(server.name)
                snapshot = ServerSnapshot(
                    server_name=server.name,
                    status=status,
                    collected_at=previous.collected_at if previous else None,
                    metrics=previous.metrics if previous else None,
                    error=message,
                )
            self._snapshots[server.name] = snapshot
            return snapshot

    async def refresh(self, servers: list[ServerConfig]) -> dict[str, ServerSnapshot]:
        snapshots = await asyncio.gather(*(self._collect_one(server) for server in servers))
        return {snapshot.server_name: snapshot for snapshot in snapshots}

