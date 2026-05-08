"""Rol tabanlı erişim denetimi (RBAC).

Tool seviyesi: hangi rol hangi tool'u çağırabilir. `tool` decorator'ı
`required_roles` parametresi alır; `RBACGuard` bağlam içinde aktif principal'ın
rollerine bakarak izin verir/reddeder.
"""
from __future__ import annotations

import contextvars
from dataclasses import dataclass, field

from ..exceptions import AuraOSError


class AuthorizationError(AuraOSError):
    """Yetki yok."""


@dataclass(frozen=True)
class Principal:
    user_id: str
    roles: frozenset[str] = field(default_factory=frozenset)
    tenant_id: str | None = None

    def has_any(self, roles: frozenset[str] | set[str] | tuple[str, ...]) -> bool:
        return bool(self.roles & set(roles))


_current: contextvars.ContextVar[Principal | None] = contextvars.ContextVar(
    "principal", default=None
)


def set_principal(p: Principal | None) -> None:
    _current.set(p)


def get_principal() -> Principal | None:
    return _current.get()


class RBACGuard:
    """Tool registry'ye verilebilir; `check(tool_name, required_roles)` çağrılır."""

    def __init__(self, *, deny_when_missing: bool = True) -> None:
        self.deny_when_missing = deny_when_missing

    def check(self, tool_name: str, required_roles: frozenset[str] | None) -> None:
        if not required_roles:
            return
        p = get_principal()
        if p is None:
            if self.deny_when_missing:
                raise AuthorizationError(f"tool '{tool_name}': principal yok, gerekli rol: {sorted(required_roles)}")
            return
        if not p.has_any(required_roles):
            raise AuthorizationError(
                f"tool '{tool_name}': '{p.user_id}' yetkili değil. "
                f"Gerekli rollerden biri: {sorted(required_roles)}, sahip olunan: {sorted(p.roles)}"
            )
