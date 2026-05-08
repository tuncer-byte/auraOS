"""Workflow node definitions and decorators."""
from __future__ import annotations

import asyncio
import inspect
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from auraos.workflow.state import WorkflowState


@dataclass
class NodeResult:
    """Result of a node execution."""
    success: bool
    output: Any = None
    error: str | None = None
    next_nodes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, output: Any = None, next_nodes: list[str] | str | None = None, **metadata) -> "NodeResult":
        """Create a successful result."""
        if isinstance(next_nodes, str):
            next_nodes = [next_nodes]
        return cls(success=True, output=output, next_nodes=next_nodes or [], metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata) -> "NodeResult":
        """Create a failed result."""
        return cls(success=False, error=error, metadata=metadata)


@dataclass
class NodeConfig:
    """Node configuration from decorator."""
    name: str | None = None
    timeout: float | None = None
    retries: int = 0
    retry_delay: float = 1.0
    on_success: str | list[str] | None = None
    on_failure: str | None = None
    requires_approval: bool = False


class Node(ABC):
    """Base class for workflow nodes."""

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        config: NodeConfig | None = None,
    ) -> None:
        self.id = id or str(uuid.uuid4())[:8]
        self.name = name or self.__class__.__name__
        self.config = config or NodeConfig()

    @abstractmethod
    async def execute(self, ctx: "WorkflowState") -> NodeResult:
        """Execute the node logic."""
        ...

    async def run(self, ctx: "WorkflowState") -> NodeResult:
        """Run with retry and timeout handling."""
        attempts = 0
        last_error = None

        while attempts <= self.config.retries:
            try:
                if self.config.timeout:
                    result = await asyncio.wait_for(
                        self.execute(ctx),
                        timeout=self.config.timeout,
                    )
                else:
                    result = await self.execute(ctx)

                if result.success:
                    if not result.next_nodes and self.config.on_success:
                        if isinstance(self.config.on_success, str):
                            result.next_nodes = [self.config.on_success]
                        else:
                            result.next_nodes = list(self.config.on_success)
                elif not result.next_nodes and self.config.on_failure:
                    result.next_nodes = [self.config.on_failure]

                return result

            except asyncio.TimeoutError:
                last_error = f"Node {self.name} timed out after {self.config.timeout}s"
            except Exception as e:
                last_error = str(e)

            attempts += 1
            if attempts <= self.config.retries:
                await asyncio.sleep(self.config.retry_delay * attempts)

        result = NodeResult.fail(last_error or "Unknown error")
        if self.config.on_failure:
            result.next_nodes = [self.config.on_failure]
        return result


class FunctionNode(Node):
    """Node wrapping a function."""

    def __init__(
        self,
        func: Callable,
        id: str | None = None,
        name: str | None = None,
        config: NodeConfig | None = None,
    ) -> None:
        super().__init__(id=id, name=name or func.__name__, config=config)
        self.func = func

    async def execute(self, ctx: "WorkflowState") -> NodeResult:
        if inspect.iscoroutinefunction(self.func):
            result = await self.func(ctx)
        else:
            result = self.func(ctx)

        if asyncio.iscoroutine(result):
            result = await result

        if isinstance(result, NodeResult):
            return result
        elif isinstance(result, dict):
            return NodeResult.ok(output=result)
        elif result is None:
            return NodeResult.ok()
        else:
            return NodeResult.ok(output=result)


def node(
    func: Callable | None = None,
    *,
    name: str | None = None,
    timeout: float | None = None,
    retries: int = 0,
    retry_delay: float = 1.0,
    on_success: str | list[str] | None = None,
    on_failure: str | None = None,
) -> Callable:
    """Decorator to mark a method as a workflow node.

    Usage:
        @node  # Without arguments
        async def my_node(self, ctx):
            return {"result": "value"}

        @node(on_success="next_step", on_failure="error_handler")  # With arguments
        async def my_node(self, ctx):
            return {"result": "value"}
    """
    def decorator(f: Callable) -> Callable:
        config = NodeConfig(
            name=name,
            timeout=timeout,
            retries=retries,
            retry_delay=retry_delay,
            on_success=on_success,
            on_failure=on_failure,
        )

        @wraps(f)
        async def wrapper(self, ctx: "WorkflowState") -> NodeResult:
            node_instance = FunctionNode(
                func=lambda c: f(self, c),
                name=name or f.__name__,
                config=config,
            )
            return await node_instance.run(ctx)

        wrapper.__auraos_node__ = True
        wrapper.__auraos_node_config__ = config
        wrapper.__auraos_node_name__ = name or f.__name__
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
