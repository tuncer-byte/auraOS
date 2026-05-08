"""Branching logic helpers for workflows."""
from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable, TYPE_CHECKING

from auraos.workflow.node import NodeResult

if TYPE_CHECKING:
    from auraos.workflow.state import WorkflowState


def condition(
    branches: dict[str, str],
    default: str | None = None,
) -> Callable:
    """Decorator for condition nodes that route to different branches.

    The decorated function should return a string key matching one of the branches.

    Usage:
        @condition(branches={"low": "approve", "medium": "review", "high": "reject"})
        def risk_assessment(self, ctx):
            if ctx.risk_score < 30:
                return "low"
            elif ctx.risk_score < 70:
                return "medium"
            return "high"
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx: "WorkflowState") -> NodeResult:
            if inspect.iscoroutinefunction(func):
                result = await func(self, ctx)
            else:
                result = func(self, ctx)

            branch_key = str(result)
            next_node = branches.get(branch_key, default)

            if next_node is None:
                return NodeResult.fail(
                    f"Condition returned '{branch_key}' but no matching branch found. "
                    f"Available: {list(branches.keys())}"
                )

            return NodeResult.ok(
                output={"branch": branch_key},
                next_nodes=[next_node],
            )

        wrapper.__auraos_node__ = True
        wrapper.__auraos_node_config__ = None
        wrapper.__auraos_node_name__ = func.__name__
        wrapper.__auraos_condition__ = True
        wrapper.__auraos_branches__ = branches
        return wrapper

    return decorator


def approval(
    timeout_hours: float = 48,
    escalate_to: str | None = None,
    on_approve: str | None = None,
    on_reject: str | None = None,
) -> Callable:
    """Decorator for human-in-the-loop approval nodes.

    The workflow will pause at this node until approval is received.

    Usage:
        @approval(timeout_hours=24, on_approve="process", on_reject="cancel")
        async def manager_review(self, ctx):
            return ctx.approval_decision  # "approved" or "rejected"
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx: "WorkflowState") -> NodeResult:
            if not ctx.get("_approval_submitted"):
                return NodeResult(
                    success=True,
                    output={"status": "awaiting_approval"},
                    metadata={
                        "requires_approval": True,
                        "timeout_hours": timeout_hours,
                        "escalate_to": escalate_to,
                    },
                )

            if inspect.iscoroutinefunction(func):
                decision = await func(self, ctx)
            else:
                decision = func(self, ctx)

            if decision == "approved" and on_approve:
                return NodeResult.ok(output={"approved": True}, next_nodes=[on_approve])
            elif decision == "rejected" and on_reject:
                return NodeResult.ok(output={"approved": False}, next_nodes=[on_reject])
            elif decision == "approved":
                return NodeResult.ok(output={"approved": True})
            else:
                return NodeResult.ok(output={"approved": False, "reason": decision})

        wrapper.__auraos_node__ = True
        wrapper.__auraos_node_config__ = None
        wrapper.__auraos_node_name__ = func.__name__
        wrapper.__auraos_approval__ = True
        wrapper.__auraos_approval_config__ = {
            "timeout_hours": timeout_hours,
            "escalate_to": escalate_to,
            "on_approve": on_approve,
            "on_reject": on_reject,
        }
        return wrapper

    return decorator


def parallel(*node_names: str, merge: str | None = None) -> Callable:
    """Decorator for parallel fan-out execution.

    Executes multiple nodes in parallel and optionally merges results.

    Usage:
        @parallel("kyc_check", "aml_check", "credit_check", merge="combine_results")
        def start_parallel_checks(self, ctx):
            return {}  # Initial context for parallel nodes
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx: "WorkflowState") -> NodeResult:
            if inspect.iscoroutinefunction(func):
                result = await func(self, ctx)
            else:
                result = func(self, ctx)

            return NodeResult.ok(
                output=result if isinstance(result, dict) else {},
                next_nodes=list(node_names),
                parallel_execution=True,
                merge_node=merge,
            )

        wrapper.__auraos_node__ = True
        wrapper.__auraos_node_config__ = None
        wrapper.__auraos_node_name__ = func.__name__
        wrapper.__auraos_parallel__ = True
        wrapper.__auraos_parallel_nodes__ = node_names
        wrapper.__auraos_merge_node__ = merge
        return wrapper

    return decorator


def merge(from_nodes: list[str]) -> Callable:
    """Decorator for merge nodes that combine parallel results.

    Usage:
        @merge(from_nodes=["kyc_check", "aml_check", "credit_check"])
        def combine_results(self, ctx):
            return {
                "all_passed": all([
                    ctx.node_outputs.get("kyc_check", {}).get("passed"),
                    ctx.node_outputs.get("aml_check", {}).get("passed"),
                    ctx.node_outputs.get("credit_check", {}).get("passed"),
                ])
            }
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx: "WorkflowState") -> NodeResult:
            missing = [n for n in from_nodes if n not in ctx.node_outputs]
            if missing:
                return NodeResult.fail(
                    f"Merge node waiting for: {missing}"
                )

            if inspect.iscoroutinefunction(func):
                result = await func(self, ctx)
            else:
                result = func(self, ctx)

            if isinstance(result, NodeResult):
                return result
            return NodeResult.ok(output=result if isinstance(result, dict) else {})

        wrapper.__auraos_node__ = True
        wrapper.__auraos_node_config__ = None
        wrapper.__auraos_node_name__ = func.__name__
        wrapper.__auraos_merge__ = True
        wrapper.__auraos_merge_from__ = from_nodes
        return wrapper

    return decorator
