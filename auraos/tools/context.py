"""Tool execution context for tool composition and service access."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, TYPE_CHECKING

from auraos.exceptions import ToolError

if TYPE_CHECKING:
    from auraos.tools.registry import ToolRegistry


@dataclass
class ToolExecutionContext:
    """Context passed to composable tools.

    Allows tools to:
    - Call other tools (composition)
    - Access registered services
    - Track call depth to prevent infinite recursion

    Usage:
        @tool(composable=True)
        def process_customer(customer_id: str, ctx: ToolExecutionContext) -> dict:
            kyc = ctx.call("validate_tc_kimlik", tc=customer_id)
            aml = ctx.call("aml_assessment", customer_id=customer_id)
            return {"kyc": kyc, "aml": aml}
    """
    registry: "ToolRegistry"
    session_id: str | None = None
    correlation_id: str | None = None
    parent_tool: str | None = None
    depth: int = 0
    max_depth: int = 5
    services: dict[type, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def call(self, tool_name: str, **kwargs: Any) -> Any:
        """Synchronously call another tool.

        Args:
            tool_name: Name of the tool to call
            **kwargs: Arguments to pass to the tool

        Returns:
            Tool result

        Raises:
            ToolError: If max depth exceeded or tool not found
        """
        if self.depth >= self.max_depth:
            raise ToolError("context", f"Max tool depth ({self.max_depth}) exceeded")

        child_ctx = replace(
            self,
            parent_tool=tool_name,
            depth=self.depth + 1,
        )

        return self.registry.invoke(tool_name, kwargs, context=child_ctx)

    async def acall(self, tool_name: str, **kwargs: Any) -> Any:
        """Asynchronously call another tool.

        Args:
            tool_name: Name of the tool to call
            **kwargs: Arguments to pass to the tool

        Returns:
            Tool result

        Raises:
            ToolError: If max depth exceeded or tool not found
        """
        if self.depth >= self.max_depth:
            raise ToolError("context", f"Max tool depth ({self.max_depth}) exceeded")

        child_ctx = replace(
            self,
            parent_tool=tool_name,
            depth=self.depth + 1,
        )

        return await self.registry.ainvoke(tool_name, kwargs, context=child_ctx)

    def get_service(self, service_type: type) -> Any:
        """Get a registered service by type.

        Args:
            service_type: The type/interface of the service

        Returns:
            The registered service instance

        Raises:
            ToolError: If service not registered
        """
        service = self.services.get(service_type)
        if service is None:
            raise ToolError("context", f"Service {service_type.__name__} not registered")
        return service

    def has_service(self, service_type: type) -> bool:
        """Check if a service is registered."""
        return service_type in self.services


def create_context(
    registry: "ToolRegistry",
    session_id: str | None = None,
    correlation_id: str | None = None,
    services: dict[type, Any] | None = None,
) -> ToolExecutionContext:
    """Create a new tool execution context.

    Args:
        registry: The tool registry
        session_id: Optional session ID
        correlation_id: Optional correlation ID
        services: Optional service mappings

    Returns:
        A new ToolExecutionContext
    """
    return ToolExecutionContext(
        registry=registry,
        session_id=session_id,
        correlation_id=correlation_id,
        services=services or {},
    )
