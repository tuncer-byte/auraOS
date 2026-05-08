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

Composable tool (tool calling tools):
    @tool(composable=True)
    def process_customer(customer_id: str, ctx: ToolExecutionContext) -> dict:
        kyc = ctx.call("validate_tc_kimlik", tc=customer_id)
        return {"kyc": kyc}
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
    composable: bool = False,
    streaming: bool = False,
) -> Callable:
    """Fonksiyonu agent tool'una dönüştürür.

    Args:
        requires_approval: Çağrı öncesi human-in-the-loop onay gerekir.
        required_roles: RBAC için gerekli rollerden en az biri.
        idempotent: Aynı argümanlarla tekrar çağrı varsa cache'lenmiş sonuç döner.
        composable: Tool, diğer tool'ları çağırabilir (ctx parametresi alır).
        streaming: Tool, async generator olarak sonuç stream eder.
    """

    def wrap(f: Callable) -> Callable:
        schema = schema_from_function(f)
        if name:
            schema.name = name
        if description:
            schema.description = description

        if composable and "ctx" in schema.parameters.get("properties", {}):
            del schema.parameters["properties"]["ctx"]
            if "ctx" in schema.parameters.get("required", []):
                schema.parameters["required"].remove("ctx")

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
        wrapper.__auraos_composable__ = composable
        wrapper.__auraos_streaming__ = streaming
        return wrapper

    if func is None:
        return wrap
    return wrap(func)


def streaming_tool(
    func: Optional[Callable] = None,
    **kwargs,
) -> Callable:
    """Async generator tool - sonuçları stream eder.

    Usage:
        @streaming_tool
        async def search_large_dataset(query: str):
            async for result in database.stream_search(query):
                yield {"match": result}
    """
    kwargs["streaming"] = True
    return tool(func, **kwargs)


def is_tool(obj: Any) -> bool:
    return callable(obj) and getattr(obj, "__auraos_tool__", False)
