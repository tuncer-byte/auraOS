"""Append-only audit log with hash-chain integrity.

Banking & compliance use-case: kim, ne zaman, hangi araçla, hangi parametrelerle,
hangi sonuçla — değişmez kayıt. Her satır önceki satırın hash'ini içerir, böylece
ortadan kayıt çıkartmak ya da değiştirmek zincir doğrulamada yakalanır.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GENESIS_HASH = "0" * 64


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class AuditRecord:
    seq: int
    ts: str
    actor: str
    action: str
    resource: str
    outcome: str  # ok | error | denied
    correlation_id: str | None = None
    session_id: str | None = None
    tenant_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    prev_hash: str = GENESIS_HASH
    hash: str = ""

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "outcome": self.outcome,
            "correlation_id": self.correlation_id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "details": self.details,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
        }

    def compute_hash(self) -> str:
        body = {k: v for k, v in self.to_dict().items() if k != "hash"}
        return _sha256(_canonical(body))


class AuditLog:
    """Append-only JSONL audit log with hash-chain.

    Default: dosyaya yazar (rotasyon dışında). Yazımı serialize eder. Read-only
    doğrulama için `verify()` zinciri baştan sona kontrol eder.
    """

    def __init__(self, path: str | os.PathLike[str] = "logs/audit.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._seq, self._last_hash = self._tail()

    def _tail(self) -> tuple[int, str]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return 0, GENESIS_HASH
        last_line = ""
        with self.path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            chunk = min(4096, size)
            f.seek(size - chunk)
            tail = f.read().decode("utf-8", errors="replace").strip().splitlines()
            if tail:
                last_line = tail[-1]
        if not last_line:
            return 0, GENESIS_HASH
        rec = json.loads(last_line)
        return int(rec["seq"]), rec["hash"]

    def write(
        self,
        *,
        actor: str,
        action: str,
        resource: str,
        outcome: str = "ok",
        correlation_id: str | None = None,
        session_id: str | None = None,
        tenant_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditRecord:
        with self._lock:
            self._seq += 1
            rec = AuditRecord(
                seq=self._seq,
                ts=_utcnow_iso(),
                actor=actor,
                action=action,
                resource=resource,
                outcome=outcome,
                correlation_id=correlation_id,
                session_id=session_id,
                tenant_id=tenant_id,
                details=details or {},
                prev_hash=self._last_hash,
            )
            h = rec.compute_hash()
            rec = AuditRecord(**{**rec.to_dict(), "hash": h})
            self._last_hash = h
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
            return rec

    def verify(self) -> tuple[bool, list[str]]:
        """Tüm zinciri yeniden hesaplayıp doğrular. (ok, hata listesi)."""
        errors: list[str] = []
        prev = GENESIS_HASH
        if not self.path.exists():
            return True, errors
        with self.path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec["prev_hash"] != prev:
                    errors.append(f"line {i}: prev_hash mismatch (expected {prev[:8]}, got {rec['prev_hash'][:8]})")
                expected = _sha256(_canonical({k: v for k, v in rec.items() if k != "hash"}))
                if rec["hash"] != expected:
                    errors.append(f"line {i}: hash mismatch")
                prev = rec["hash"]
        return (not errors), errors

    def tail(self, n: int = 50) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-n:]
        return [json.loads(l) for l in lines if l.strip()]
