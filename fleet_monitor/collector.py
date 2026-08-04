from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from .models import Metrics


class CollectionError(RuntimeError):
    """Falha ao obter ou interpretar métricas remotas."""


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


class RemoteExecutor(Protocol):
    def run(self, command: str) -> CommandResult: ...


def _parse_payload(payload: str, expected_method: str) -> Metrics:
    try:
        data = json.loads(payload)
        data["method"] = expected_method
        return Metrics.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise CollectionError("resposta remota inválida") from exc


def parse_psutil_payload(payload: str) -> Metrics:
    return _parse_payload(payload, "psutil")


def parse_fallback_payload(payload: str) -> Metrics:
    return _parse_payload(payload, "fallback")


def sanitize(message: str) -> str:
    message = re.sub(r"(?i)(password|senha)\s*[:=]\s*\S+", r"\1=<redacted>", message)
    return message.strip()[:500]


PSUTIL_PROBE = r'''python3 - <<'PY'
import json, os, time
import psutil

disks = []
for part in psutil.disk_partitions(all=False):
    try:
        usage = psutil.disk_usage(part.mountpoint)
        disks.append({"mountpoint": part.mountpoint, "percent": usage.percent,
                      "total_bytes": usage.total, "used_bytes": usage.used})
    except (PermissionError, OSError):
        pass

interfaces = [{"name": name, "bytes_sent": value.bytes_sent,
               "bytes_recv": value.bytes_recv}
              for name, value in psutil.net_io_counters(pernic=True).items()]
processes = []
for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
    try:
        processes.append(proc.info)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
processes.sort(key=lambda item: (item.get("cpu_percent") or 0,
                                 item.get("memory_percent") or 0), reverse=True)

vm, swap = psutil.virtual_memory(), psutil.swap_memory()
print(json.dumps({"method": "psutil", "cpu_percent": psutil.cpu_percent(interval=0.2),
  "memory_percent": vm.percent, "swap_percent": swap.percent,
  "load_average": list(os.getloadavg()), "uptime_seconds": time.time() - psutil.boot_time(),
  "disks": disks, "interfaces": interfaces, "processes": processes[:10]}))
PY'''


FALLBACK_PROBE = r'''python3 - <<'PY'
import json, os, subprocess

def read(path):
    try:
        with open(path, encoding="utf-8") as stream:
            return stream.read()
    except OSError:
        return ""

mem = {}
for line in read("/proc/meminfo").splitlines():
    key, _, raw = line.partition(":")
    try: mem[key] = int(raw.strip().split()[0]) * 1024
    except (ValueError, IndexError): pass
total, available = mem.get("MemTotal"), mem.get("MemAvailable")
memory_percent = round((1 - available / total) * 100, 2) if total and available is not None else None
swap_total, swap_free = mem.get("SwapTotal"), mem.get("SwapFree")
swap_percent = round((1 - swap_free / swap_total) * 100, 2) if swap_total else 0.0

disks = []
try:
    output = subprocess.check_output(["df", "-B1", "-P"], text=True, stderr=subprocess.DEVNULL)
    for line in output.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 6 and fields[4].endswith("%"):
            disks.append({"mountpoint": fields[5], "total_bytes": int(fields[1]),
                          "used_bytes": int(fields[2]), "percent": float(fields[4][:-1])})
except (OSError, subprocess.SubprocessError, ValueError): pass

failed = []
try:
    output = subprocess.check_output(["systemctl", "--failed", "--no-legend", "--plain"],
                                     text=True, stderr=subprocess.DEVNULL)
    failed = [line.split()[0] for line in output.splitlines() if line.split()]
except (OSError, subprocess.SubprocessError): pass

ports = []
try:
    output = subprocess.check_output(["ss", "-lntuH"], text=True, stderr=subprocess.DEVNULL)
    ports = [line.split()[4] for line in output.splitlines() if len(line.split()) >= 5]
except (OSError, subprocess.SubprocessError): pass

try: uptime = float(read("/proc/uptime").split()[0])
except (ValueError, IndexError): uptime = None
try: load = list(os.getloadavg())
except OSError: load = None

print(json.dumps({"method": "fallback", "cpu_percent": None,
  "memory_percent": memory_percent, "swap_percent": swap_percent,
  "load_average": load, "uptime_seconds": uptime, "disks": disks,
  "failed_services": failed, "listening_ports": ports}))
PY'''


class HybridCollector:
    def collect(self, executor: RemoteExecutor) -> Metrics:
        primary = executor.run(PSUTIL_PROBE)
        if primary.exit_code == 0:
            return parse_psutil_payload(primary.stdout)

        fallback = executor.run(FALLBACK_PROBE)
        if fallback.exit_code != 0:
            detail = sanitize(fallback.stderr)
            raise CollectionError(detail or "coleta remota falhou")
        return parse_fallback_payload(fallback.stdout)

