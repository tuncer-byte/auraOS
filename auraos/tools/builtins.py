"""
Built-in tools — autonomous agent için filesystem ve shell işlemleri.
Hepsi sandbox üzerinden çalışır; workspace dışına çıkış yasaktır.
"""
from __future__ import annotations
from typing import Callable

from auraos.tools.decorator import tool
from auraos.sandbox.workspace import Workspace
from auraos.sandbox.shell import SafeShell


def file_tools(workspace: Workspace) -> list[Callable]:
    """Workspace'e bağlı dosya tool'ları üretir."""

    @tool
    def read_file(path: str) -> str:
        """
        Workspace içindeki bir dosyayı okur.

        Args:
            path: Workspace'e göre relatif yol.
        """
        return workspace.read_text(path)

    @tool
    def write_file(path: str, content: str) -> str:
        """
        Workspace içine bir dosya yazar (varsa üzerine yazar).

        Args:
            path: Workspace'e göre relatif yol.
            content: Dosya içeriği.
        """
        workspace.write_text(path, content)
        return f"yazıldı: {path}"

    @tool
    def list_dir(path: str = ".") -> list[str]:
        """
        Workspace içindeki bir dizini listeler.

        Args:
            path: Listelenecek dizin (varsayılan kök).
        """
        return workspace.list_dir(path)

    @tool
    def delete_file(path: str) -> str:
        """
        Workspace içindeki bir dosyayı siler.

        Args:
            path: Silinecek dosya yolu.
        """
        workspace.delete(path)
        return f"silindi: {path}"

    return [read_file, write_file, list_dir, delete_file]


def shell_tools(shell: SafeShell) -> list[Callable]:
    """Sandbox'lı shell tool'u."""

    @tool(requires_approval=True)
    def run_shell(command: str, timeout: int = 30) -> dict:
        """
        Workspace içinde güvenli shell komutu çalıştırır.

        Args:
            command: Çalıştırılacak komut.
            timeout: Saniye cinsinden zaman aşımı.
        """
        return shell.run(command, timeout=timeout)

    return [run_shell]
