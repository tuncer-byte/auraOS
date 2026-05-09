"""
Session yönetimi - çok turlu konuşma için.

Backend'ler:
  - InMemorySessionStore (geliştirme/test)
  - RedisSessionStore (production)

Her session: id, mesaj listesi, metadata, TTL.
"""
from __future__ import annotations
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from auraos.exceptions import SessionExpiredError, SessionNotFoundError


@dataclass
class Session:
    session_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def add_message(self, role: str, content: str, **extra: Any) -> None:
        msg = {"role": role, "content": content}
        msg.update(extra)
        self.messages.append(msg)
        self.last_active = time.time()

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.messages[-limit:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "messages": self.messages,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_active": self.last_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        return cls(
            session_id=data["session_id"],
            messages=data.get("messages", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            last_active=data.get("last_active", time.time()),
        )


class SessionStore(Protocol):
    def get(self, session_id: str) -> Optional[Session]: ...
    def save(self, session: Session) -> None: ...
    def delete(self, session_id: str) -> None: ...


class InMemorySessionStore:
    def __init__(self, ttl_seconds: float = 3600.0):
        self.ttl = ttl_seconds
        self._sessions: dict[str, Session] = {}

    def _expired(self, session: Session) -> bool:
        return self.ttl > 0 and (time.time() - session.last_active) > self.ttl

    def get(self, session_id: str) -> Optional[Session]:
        s = self._sessions.get(session_id)
        if s is None:
            return None
        if self._expired(s):
            self._sessions.pop(session_id, None)
            return None
        return s

    def save(self, session: Session) -> None:
        self._sessions[session.session_id] = session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


class RedisSessionStore:
    def __init__(self, url: str = "redis://localhost:6379/0", ttl_seconds: float = 3600.0, prefix: str = "auraos:session:"):
        import redis  # type: ignore
        self._client = redis.Redis.from_url(url, decode_responses=True)
        self.ttl = ttl_seconds
        self.prefix = prefix

    def _k(self, sid: str) -> str:
        return f"{self.prefix}{sid}"

    def get(self, session_id: str) -> Optional[Session]:
        raw = self._client.get(self._k(session_id))
        if raw is None:
            return None
        return Session.from_dict(json.loads(raw))

    def save(self, session: Session) -> None:
        payload = json.dumps(session.to_dict(), default=str)
        if self.ttl > 0:
            self._client.setex(self._k(session.session_id), int(self.ttl), payload)
        else:
            self._client.set(self._k(session.session_id), payload)

    def delete(self, session_id: str) -> None:
        self._client.delete(self._k(session_id))


class SQLiteSessionStore:
    def __init__(self, db_path: str = "auraos_sessions.db", ttl_seconds: float = 86400.0):
        import sqlite3
        import threading
        self.ttl = ttl_seconds
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS sessions ("
            "  session_id TEXT PRIMARY KEY,"
            "  data TEXT NOT NULL,"
            "  created_at REAL NOT NULL,"
            "  last_active REAL NOT NULL"
            ")"
        )
        self._conn.commit()

    def get(self, session_id: str) -> Optional[Session]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT data, last_active FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        data_str, last_active = row
        if self.ttl > 0 and (time.time() - last_active) > self.ttl:
            self.delete(session_id)
            return None
        return Session.from_dict(json.loads(data_str))

    def save(self, session: Session) -> None:
        session.last_active = time.time()
        payload = json.dumps(session.to_dict(), default=str)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO sessions (session_id, data, created_at, last_active) "
                "VALUES (?, ?, ?, ?)",
                (session.session_id, payload, session.created_at, session.last_active),
            )
            self._conn.commit()

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            self._conn.commit()

    def cleanup_expired(self) -> int:
        if self.ttl <= 0:
            return 0
        cutoff = time.time() - self.ttl
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM sessions WHERE last_active < ?", (cutoff,)
            )
            self._conn.commit()
            return cur.rowcount


class SessionManager:
    """
    Session lifecycle wrapper.

    Örnek:
        sm = SessionManager()
        s = sm.get_or_create("user_123")
        s.add_message("user", "Merhaba")
        sm.save(s)
    """

    def __init__(self, store: Optional[SessionStore] = None, max_messages: int = 50):
        self.store = store or InMemorySessionStore()
        self.max_messages = max_messages

    def create(self, session_id: Optional[str] = None, metadata: Optional[dict[str, Any]] = None) -> Session:
        sid = session_id or uuid.uuid4().hex
        session = Session(session_id=sid, metadata=metadata or {})
        self.store.save(session)
        return session

    def get(self, session_id: str, *, raise_if_missing: bool = False) -> Optional[Session]:
        s = self.store.get(session_id)
        if s is None and raise_if_missing:
            raise SessionNotFoundError(f"Session not found: {session_id}")
        return s

    def get_or_create(self, session_id: str, metadata: Optional[dict[str, Any]] = None) -> Session:
        s = self.get(session_id)
        if s is not None:
            return s
        return self.create(session_id=session_id, metadata=metadata)

    def save(self, session: Session) -> None:
        # Sliding window trimming
        if self.max_messages and len(session.messages) > self.max_messages:
            session.messages = session.messages[-self.max_messages:]
        self.store.save(session)

    def delete(self, session_id: str) -> None:
        self.store.delete(session_id)
