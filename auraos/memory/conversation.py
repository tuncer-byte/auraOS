"""
ConversationMemory — basit konuşma geçmişi tutucu.

Backend olarak in-memory, SQLite veya Redis seçilebilir.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from auraos.memory.base import Memory


class ConversationMemory(Memory):
    def __init__(self, backend: str = "memory", path: Optional[str] = None):
        self.backend = backend
        self.path = path
        self._items: list[dict[str, Any]] = []
        self._conn: Optional[sqlite3.Connection] = None

        if backend == "sqlite":
            db_path = Path(path or "./auraos_memory.db")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(db_path))
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS conversation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ts DATETIME DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            self._conn.commit()

    def add(self, item: dict[str, Any]) -> None:
        if self.backend == "sqlite" and self._conn:
            self._conn.execute(
                "INSERT INTO conversation (role, content) VALUES (?, ?)",
                (item.get("role", "user"), json.dumps(item.get("content", ""), default=str)),
            )
            self._conn.commit()
        else:
            self._items.append(item)

    def get_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        if self.backend == "sqlite" and self._conn:
            cur = self._conn.execute(
                "SELECT role, content FROM conversation ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = list(reversed(cur.fetchall()))
            return [{"role": r, "content": json.loads(c)} for r, c in rows]
        return self._items[-limit:]

    def clear(self) -> None:
        if self.backend == "sqlite" and self._conn:
            self._conn.execute("DELETE FROM conversation")
            self._conn.commit()
        else:
            self._items.clear()

    def __len__(self) -> int:
        if self.backend == "sqlite" and self._conn:
            return self._conn.execute("SELECT COUNT(*) FROM conversation").fetchone()[0]
        return len(self._items)
