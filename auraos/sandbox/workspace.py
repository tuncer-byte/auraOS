"""
Workspace — sandbox'lı dosya sistemi katmanı.

Tüm işlemler `root` dizinine sınırlanır. Path traversal (..),
sembolik link kaçışı ve mutlak yol kullanımı engellenir.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional


class WorkspaceSecurityError(Exception):
    pass


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str | Path) -> Path:
        """Path'i workspace içinde olduğunu doğrulayarak çöz."""
        p = Path(path)
        if p.is_absolute():
            raise WorkspaceSecurityError(f"Mutlak yol yasak: {path}")

        full = (self.root / p).resolve()
        try:
            full.relative_to(self.root)
        except ValueError:
            raise WorkspaceSecurityError(
                f"Path workspace dışında: {path}"
            )
        return full

    def read_text(self, path: str) -> str:
        return self._resolve(path).read_text(encoding="utf-8")

    def write_text(self, path: str, content: str) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def list_dir(self, path: str = ".") -> list[str]:
        full = self._resolve(path)
        if not full.is_dir():
            raise NotADirectoryError(path)
        return sorted(p.name for p in full.iterdir())

    def delete(self, path: str) -> None:
        target = self._resolve(path)
        if target.is_file():
            target.unlink()
        elif target.is_dir():
            import shutil
            shutil.rmtree(target)

    def exists(self, path: str) -> bool:
        try:
            return self._resolve(path).exists()
        except WorkspaceSecurityError:
            return False

    def __repr__(self) -> str:
        return f"Workspace({self.root!s})"
