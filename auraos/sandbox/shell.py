"""
SafeShell — workspace içinde, allowlist tabanlı komut yürütücü.
"""
from __future__ import annotations
import shlex
import subprocess
from typing import Optional

from auraos.sandbox.workspace import Workspace, WorkspaceSecurityError


# Tehlikeli kabul edilen komut/desen listesi.
_DANGEROUS_PATTERNS = [
    "rm -rf /", "mkfs", "dd if=", ":(){", "shutdown", "reboot",
    "halt", "poweroff", "chmod 777 /", "> /dev/sda", "fdisk",
    "curl | sh", "wget | sh", "sudo", "passwd", "useradd",
]

# Güvenli kabul edilen komutlar (program adı bazında).
_DEFAULT_ALLOWLIST = {
    "ls", "cat", "echo", "pwd", "head", "tail", "wc", "grep",
    "find", "python", "python3", "pip", "pytest", "git", "node",
    "npm", "jq", "awk", "sed", "sort", "uniq", "cut", "tr",
}


class SafeShell:
    def __init__(
        self,
        workspace: Workspace,
        allowlist: Optional[set[str]] = None,
    ):
        self.workspace = workspace
        self.allowlist = set(allowlist) if allowlist else _DEFAULT_ALLOWLIST.copy()

    def _check(self, command: str) -> None:
        low = command.lower()
        for pattern in _DANGEROUS_PATTERNS:
            if pattern in low:
                raise WorkspaceSecurityError(
                    f"Tehlikeli komut bloklandı: {pattern}"
                )

        try:
            tokens = shlex.split(command)
        except ValueError as e:
            raise WorkspaceSecurityError(f"Geçersiz komut: {e}")

        if not tokens:
            raise WorkspaceSecurityError("Boş komut")

        program = tokens[0].split("/")[-1]
        if program not in self.allowlist:
            raise WorkspaceSecurityError(
                f"Komut allowlist'te değil: {program}"
            )

    def run(self, command: str, timeout: int = 30) -> dict:
        """Workspace içinde komut çalıştır."""
        self._check(command)
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(self.workspace.root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "TIMEOUT", "returncode": -1}
