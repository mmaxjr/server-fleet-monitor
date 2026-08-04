import json

import pytest

from fleet_monitor.collector import (
    CollectionError,
    CommandResult,
    HybridCollector,
    parse_fallback_payload,
    parse_psutil_payload,
)


PSUTIL_PAYLOAD = json.dumps(
    {
        "method": "psutil",
        "cpu_percent": 12.5,
        "memory_percent": 42.0,
        "swap_percent": 3.0,
        "load_average": [0.1, 0.2, 0.3],
        "uptime_seconds": 1200,
        "disks": [{"mountpoint": "/", "percent": 61.2}],
        "interfaces": [{"name": "eth0", "bytes_sent": 10, "bytes_recv": 20}],
        "processes": [{"pid": 7, "name": "nginx", "cpu_percent": 1.0}],
    }
)


class FakeExecutor:
    def __init__(self, results: list[CommandResult]) -> None:
        self.results = iter(results)
        self.commands: list[str] = []

    def run(self, command: str) -> CommandResult:
        self.commands.append(command)
        return next(self.results)


def test_psutil_payload_is_normalized() -> None:
    metrics = parse_psutil_payload(PSUTIL_PAYLOAD)
    assert metrics.cpu_percent == 12.5
    assert metrics.memory_percent == 42.0
    assert metrics.load_average == (0.1, 0.2, 0.3)
    assert metrics.disks[0].mountpoint == "/"
    assert metrics.method == "psutil"


def test_missing_fallback_value_remains_none() -> None:
    metrics = parse_fallback_payload('{"method":"fallback","cpu_percent":null}')
    assert metrics.cpu_percent is None
    assert metrics.method == "fallback"


def test_collector_falls_back_when_psutil_is_missing() -> None:
    fallback = json.dumps({"method": "fallback", "memory_percent": 54.0})
    executor = FakeExecutor(
        [
            CommandResult(1, "", "ModuleNotFoundError: psutil"),
            CommandResult(0, fallback, ""),
        ]
    )

    metrics = HybridCollector().collect(executor)

    assert metrics.method == "fallback"
    assert metrics.memory_percent == 54.0
    assert len(executor.commands) == 2


def test_collector_reports_sanitized_failure() -> None:
    executor = FakeExecutor(
        [CommandResult(1, "", "missing"), CommandResult(1, "", "password=secret\nfailed")]
    )

    with pytest.raises(CollectionError) as error:
        HybridCollector().collect(executor)

    assert "secret" not in str(error.value)

