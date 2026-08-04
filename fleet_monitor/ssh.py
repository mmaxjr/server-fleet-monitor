from __future__ import annotations

import socket

import paramiko

from .collector import CommandResult
from .models import ServerConfig, ServerStatus


def _redact(message: str, password: str) -> str:
    return message.replace(password, "<redacted>") if password else message


def map_ssh_error(exc: Exception, password: str = "") -> tuple[ServerStatus, str]:
    if isinstance(exc, paramiko.AuthenticationException):
        return ServerStatus.AUTHENTICATION_ERROR, "autenticação SSH recusada"
    if isinstance(exc, (paramiko.BadHostKeyException, paramiko.SSHException)) and (
        isinstance(exc, paramiko.BadHostKeyException)
        or "known_hosts" in str(exc)
        or "not found in known_hosts" in str(exc)
    ):
        return ServerStatus.HOST_KEY_ERROR, "chave do host ausente ou divergente"
    if isinstance(exc, (TimeoutError, socket.timeout, paramiko.ssh_exception.NoValidConnectionsError)):
        return ServerStatus.OFFLINE, "servidor indisponível ou timeout SSH"
    return ServerStatus.COLLECTION_ERROR, _redact(str(exc), password)[:300] or "falha SSH"


class ParamikoExecutor:
    def __init__(self, server: ServerConfig, timeout: float) -> None:
        self.server = server
        self.timeout = timeout
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
        self.client.connect(
            hostname=server.host,
            port=server.port,
            username=server.username,
            password=server.password.get_secret_value(),
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
        )

    def run(self, command: str) -> CommandResult:
        _stdin, stdout, stderr = self.client.exec_command(command, timeout=self.timeout)
        exit_code = stdout.channel.recv_exit_status()
        return CommandResult(
            exit_code=exit_code,
            stdout=stdout.read().decode("utf-8", errors="replace"),
            stderr=stderr.read().decode("utf-8", errors="replace"),
        )

    def close(self) -> None:
        self.client.close()

