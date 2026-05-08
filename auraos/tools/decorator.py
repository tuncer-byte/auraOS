"""
@tool — bir Python fonksiyonunu agent tool'una dönüştüren dekoratör.

Örnek:
    @tool
    def hesapla(a: int, b: int) -> int:
        '''İki sayıyı toplar.

        Args:
            a: İlk sayı
            b: İkinci sayı
        '''
        return a + b
"""
from __future__ import annotations
from functools import wraps
from typing import Any, Callable, Optional

from auraos.tools.schema import ToolSchema, schema_from_function


def tool(
    func: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    requires_approval: bool = False,
    required_roles: Optional[frozenset[str] | set[str] | tuple[str, ...]] = None,
    idempotent: bool = False,
) -> Callable:
    """Fonksiyonu agent tool'una dönüştürür.

    Args:
        requires_approval: Çağrı öncesi human-in-the-loop onay gerekir.
        required_roles: RBAC için gerekli rollerden en az biri.
        idempotent: Aynı argümanlarla tekrar çağrı varsa cache'lenmiş sonuç döner.
    """

    def wrap(f: Callable) -> Callable:
        schema = schema_from_function(f)
        if name:
            schema.name = name
        if description:
            schema.description = description

        @wraps(f)
        def wrapper(*args, **kwargs) -> Any:
            return f(*args, **kwargs)

        wrapper.__auraos_tool__ = True
        wrapper.__auraos_schema__ = schema
        wrapper.__auraos_requires_approval__ = requires_approval
        wrapper.__auraos_required_roles__ = (
            frozenset(required_roles) if required_roles else frozenset()
        )
        wrapper.__auraos_idempotent__ = idempotent
        return wrapper

    if func is None:
        return wrap
    return wrap(func)


def is_tool(obj: Any) -> bool:
    return callable(obj) and getattr(obj, "__auraos_tool__", False)
