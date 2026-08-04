from __future__ import annotations

import asyncio

import paramiko
import pytest
from pydantic import SecretStr

from fleet_monitor.models import Metrics, ServerConfig, ServerStatus, Settings
from fleet_monitor.service import FleetService
from fleet_monitor.ssh import map_ssh_error


SERVER = ServerConfig(
    name="web", host="10.0.0.2", username="ops", password=SecretStr("secret")
)
GOOD_METRICS = Metrics(method="fallback", memory_percent=45)


class SequenceCollector:
    def __init__(self, values: list[Metrics | Exception]) -> None:
        self.values = iter(values)

    def collect(self, executor: object) -> Metrics:
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return value


class FakeExecutor:
    def close(self) -> None:
        pass


def test_authentication_error_does_not_contain_password() -> None:
    status, message = map_ssh_error(
        paramiko.AuthenticationException("password secret rejected"), "secret"
    )
    assert status is ServerStatus.AUTHENTICATION_ERROR
    assert "secret" not in message


@pytest.mark.asyncio
async def test_refresh_preserves_last_good_snapshot() -> None:
    service = FleetService(
        settings=Settings(),
        collector=SequenceCollector([GOOD_METRICS, TimeoutError()]),
        executor_factory=lambda server, timeout: FakeExecutor(),
    )

    first = await service.refresh([SERVER])
    second = await service.refresh([SERVER])

    assert second["web"].metrics == first["web"].metrics
    assert second["web"].status is ServerStatus.OFFLINE
    assert "secret" not in (second["web"].error or "")


@pytest.mark.asyncio
async def test_refresh_collects_servers_concurrently() -> None:
    active = 0
    maximum = 0

    class SlowCollector:
        def collect(self, executor: object) -> Metrics:
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            import time
            time.sleep(0.03)
            active -= 1
            return GOOD_METRICS

    servers = [SERVER.model_copy(update={"name": f"web-{index}"}) for index in range(3)]
    service = FleetService(
        settings=Settings(max_concurrency=3),
        collector=SlowCollector(),
        executor_factory=lambda server, timeout: FakeExecutor(),
    )

    await asyncio.wait_for(service.refresh(servers), timeout=1)

    assert maximum > 1

