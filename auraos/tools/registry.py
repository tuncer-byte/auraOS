"""
ToolRegistry — agent'ın çağırabileceği tool'ların kataloğu.

Özellikler:
  - Pydantic/light validation (validator.py)
  - requires_approval flag - human-in-the-loop için ToolApprovalRequired raise
  - sync ve async invoke
  - Tool başına execution timeout
"""
from __future__ import annotations
import asyncio
import inspect
import time
from typing import Any, Callable, Iterator, Optional

from auraos.exceptions import (
    ToolApprovalRequired,
    ToolExecutionError,
    ToolNotFoundError,
    ToolTimeoutError,
)
from auraos.tools.decorator import is_tool, tool as tool_decorator
from auraos.tools.schema import ToolSchema
from auraos.tools.validator import validate_tool_arguments
from auraos.utils.idempotency import IdempotencyStore, make_idempotency_key


class ApprovalCallback:
    """
    Onay backend'i için protokol-benzeri taban sınıf.

    Subclass'lar:
      - approve(tool_name, arguments) -> bool : sync onay
      - aapprove(tool_name, arguments) -> bool : async onay
    """

    def approve(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        return False

    async def aapprove(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        return await asyncio.to_thread(self.approve, tool_name, arguments)


class AlwaysApprove(ApprovalCallback):
    def approve(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        return True


class ToolRegistry:
    def __init__(
        self,
        approval_callback: Optional[ApprovalCallback] = None,
        default_timeout: Optional[float] = None,
        rbac_guard: Optional[Any] = None,
        idempotency_store: Optional[IdempotencyStore] = None,
    ):
        self._tools: dict[str, Callable] = {}
        self.approval_callback = approval_callback
        self.default_timeout = default_timeout
        self.rbac_guard = rbac_guard
        self.idempotency_store = idempotency_store

    def _check_rbac(self, func: Callable, name: str) -> None:
        if self.rbac_guard is None:
            return
        roles = getattr(func, "__auraos_required_roles__", frozenset())
        self.rbac_guard.check(name, roles or None)

    def register(self, func: Callable, name: str | None = None) -> Callable:
        if not is_tool(func):
            func = tool_decorator(func)
        tool_name = name or func.__auraos_schema__.name
        self._tools[tool_name] = func
        return func

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def _get(self, name: str) -> Callable:
        if name not in self._tools:
            raise ToolNotFoundError(name, "tool bulunamadı (not registered)")
        return self._tools[name]

    def _check_approval(self, func: Callable, name: str, arguments: dict[str, Any]) -> None:
        if not getattr(func, "__auraos_requires_approval__", False):
            return
        cb = self.approval_callback
        if cb is None:
            raise ToolApprovalRequired(name, arguments)
        if not cb.approve(name, arguments):
            from auraos.exceptions import ToolApprovalDenied
            raise ToolApprovalDenied(name, "user denied approval")

    async def _acheck_approval(self, func: Callable, name: str, arguments: dict[str, Any]) -> None:
        if not getattr(func, "__auraos_requires_approval__", False):
            return
        cb = self.approval_callback
        if cb is None:
            raise ToolApprovalRequired(name, arguments)
        if not await cb.aapprove(name, arguments):
            from auraos.exceptions import ToolApprovalDenied
            raise ToolApprovalDenied(name, "user denied approval")

    def invoke(self, name: str, arguments: dict[str, Any], timeout: Optional[float] = None) -> Any:
        func = self._get(name)
        cleaned = validate_tool_arguments(func, name, dict(arguments or {}))
        self._check_rbac(func, name)
        self._check_approval(func, name, cleaned)

        if self.idempotency_store and getattr(func, "__auraos_idempotent__", False):
            key = make_idempotency_key(name, cleaned)
            hit, val = self.idempotency_store.get(key)
            if hit:
                return val

        timeout = timeout if timeout is not None else self.default_timeout
        if timeout is None:
            result = self._safe_call(func, name, cleaned)
        else:
            result_box: dict[str, Any] = {}
            error_box: dict[str, BaseException] = {}

            def runner():
                try:
                    result_box["v"] = self._safe_call(func, name, cleaned)
                except BaseException as e:
                    error_box["e"] = e

            import threading
            t = threading.Thread(target=runner, daemon=True)
            t.start()
            t.join(timeout)
            if t.is_alive():
                raise ToolTimeoutError(name, timeout)
            if "e" in error_box:
                raise error_box["e"]
            result = result_box.get("v")

        if self.idempotency_store and getattr(func, "__auraos_idempotent__", False):
            self.idempotency_store.put(make_idempotency_key(name, cleaned), result)
        return result

    async def ainvoke(self, name: str, arguments: dict[str, Any], timeout: Optional[float] = None) -> Any:
        func = self._get(name)
        cleaned = validate_tool_arguments(func, name, dict(arguments or {}))
        self._check_rbac(func, name)
        await self._acheck_approval(func, name, cleaned)

        if self.idempotency_store and getattr(func, "__auraos_idempotent__", False):
            key = make_idempotency_key(name, cleaned)
            hit, val = self.idempotency_store.get(key)
            if hit:
                return val

        timeout = timeout if timeout is not None else self.default_timeout

        async def call() -> Any:
            if inspect.iscoroutinefunction(func):
                return await func(**cleaned)
            return await asyncio.to_thread(func, **cleaned)

        try:
            if timeout is None:
                result = await call()
            else:
                result = await asyncio.wait_for(call(), timeout=timeout)
        except asyncio.TimeoutError:
            raise ToolTimeoutError(name, timeout or 0.0)
        except (ToolApprovalRequired, ToolTimeoutError):
            raise
        except Exception as e:
            raise ToolExecutionError(name, str(e), details={"args": cleaned})

        if self.idempotency_store and getattr(func, "__auraos_idempotent__", False):
            self.idempotency_store.put(make_idempotency_key(name, cleaned), result)
        return result

    def _safe_call(self, func: Callable, name: str, cleaned: dict[str, Any]) -> Any:
        try:
            return func(**cleaned)
        except (ToolApprovalRequired, ToolTimeoutError):
            raise
        except Exception as e:
            raise ToolExecutionError(name, str(e), details={"args": cleaned})

    def schemas(self) -> list[ToolSchema]:
        return [f.__auraos_schema__ for f in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def requires_approval(self, name: str) -> bool:
        if name not in self._tools:
            return False
        return bool(getattr(self._tools[name], "__auraos_requires_approval__", False))

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self) -> Iterator[str]:
        return iter(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
