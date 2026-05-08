"""Workflow executor - runtime engine for workflows."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TYPE_CHECKING

from auraos.workflow.state import (
    WorkflowState,
    StateStore,
    InMemoryStateStore,
    ExecutionStatus,
)
from auraos.workflow.node import NodeResult

if TYPE_CHECKING:
    from auraos.workflow.workflow import Workflow
    from auraos.observability.audit import AuditLog
    from auraos.observability.metrics import MetricsRegistry


@dataclass
class WorkflowExecution:
    """Result of a workflow execution."""
    execution_id: str
    workflow_id: str
    workflow_name: str
    status: ExecutionStatus
    output: Any = None
    error: str | None = None
    nodes_executed: list[str] = field(default_factory=list)
    duration_ms: float = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    state: WorkflowState | None = None


class WorkflowExecutor:
    """Executes workflows with state persistence and observability."""

    def __init__(
        self,
        workflow: "Workflow",
        state_store: StateStore | None = None,
        audit_log: "AuditLog | None" = None,
        metrics: "MetricsRegistry | None" = None,
        max_iterations: int = 100,
    ) -> None:
        self.workflow = workflow
        self.state_store = state_store or InMemoryStateStore()
        self.audit_log = audit_log
        self.metrics = metrics
        self.max_iterations = max_iterations
        self._paused: set[str] = set()

    async def run(
        self,
        initial_context: dict[str, Any] | None = None,
        execution_id: str | None = None,
    ) -> WorkflowExecution:
        """Start a new workflow execution."""
        errors = self.workflow.validate()
        if errors:
            return WorkflowExecution(
                execution_id=execution_id or str(uuid.uuid4()),
                workflow_id=self.workflow.id,
                workflow_name=self.workflow.name,
                status=ExecutionStatus.FAILED,
                error=f"Workflow validation failed: {errors}",
            )

        state = WorkflowState(
            execution_id=execution_id or str(uuid.uuid4()),
            workflow_id=self.workflow.id,
            workflow_name=self.workflow.name,
            status=ExecutionStatus.RUNNING,
            current_node=self.workflow.entry_node,
            started_at=datetime.now(),
        )

        if initial_context:
            state.update(initial_context)

        await self.state_store.save(state)

        if self.audit_log:
            self.audit_log.record(
                action="workflow_started",
                actor="system",
                resource=self.workflow.name,
                detail={
                    "execution_id": state.execution_id,
                    "workflow_id": self.workflow.id,
                    "entry_node": self.workflow.entry_node,
                },
            )

        return await self._execute(state)

    async def resume(self, execution_id: str) -> WorkflowExecution:
        """Resume a paused workflow execution."""
        state = await self.state_store.load(execution_id)
        if not state:
            return WorkflowExecution(
                execution_id=execution_id,
                workflow_id="",
                workflow_name="",
                status=ExecutionStatus.FAILED,
                error=f"Execution {execution_id} not found",
            )

        if state.status != ExecutionStatus.PAUSED:
            return WorkflowExecution(
                execution_id=execution_id,
                workflow_id=state.workflow_id,
                workflow_name=state.workflow_name,
                status=state.status,
                error=f"Cannot resume: status is {state.status.value}",
            )

        state.status = ExecutionStatus.RUNNING
        state.paused_at = None
        self._paused.discard(execution_id)

        await self.state_store.save(state)

        if self.audit_log:
            self.audit_log.record(
                action="workflow_resumed",
                actor="system",
                resource=self.workflow.name,
                detail={"execution_id": execution_id, "node": state.current_node},
            )

        return await self._execute(state)

    def pause(self, execution_id: str) -> None:
        """Mark an execution to pause after current node."""
        self._paused.add(execution_id)

    async def cancel(self, execution_id: str) -> bool:
        """Cancel a workflow execution."""
        state = await self.state_store.load(execution_id)
        if not state:
            return False

        state.status = ExecutionStatus.CANCELLED
        state.completed_at = datetime.now()
        await self.state_store.save(state)

        if self.audit_log:
            self.audit_log.record(
                action="workflow_cancelled",
                actor="system",
                resource=self.workflow.name,
                detail={"execution_id": execution_id},
            )

        return True

    async def _execute(self, state: WorkflowState) -> WorkflowExecution:
        """Execute the workflow from current state."""
        start_time = datetime.now()
        nodes_executed: list[str] = []
        iteration = 0
        pending_nodes: list[str] = [state.current_node] if state.current_node else []

        while pending_nodes and iteration < self.max_iterations:
            iteration += 1

            if state.execution_id in self._paused:
                state.status = ExecutionStatus.PAUSED
                state.paused_at = datetime.now()
                await self.state_store.save(state)

                if self.audit_log:
                    self.audit_log.record(
                        action="workflow_paused",
                        actor="system",
                        resource=self.workflow.name,
                        detail={"execution_id": state.execution_id, "node": state.current_node},
                    )

                return WorkflowExecution(
                    execution_id=state.execution_id,
                    workflow_id=self.workflow.id,
                    workflow_name=self.workflow.name,
                    status=ExecutionStatus.PAUSED,
                    nodes_executed=nodes_executed,
                    duration_ms=(datetime.now() - start_time).total_seconds() * 1000,
                    started_at=state.started_at,
                    state=state,
                )

            current_node_name = pending_nodes.pop(0)
            state.current_node = current_node_name

            node = self.workflow.get_node(current_node_name)
            if not node:
                state.record_error(current_node_name, f"Node '{current_node_name}' not found")
                state.status = ExecutionStatus.FAILED
                break

            if self.metrics:
                self.metrics.counter("auraos_workflow_node_started").inc()

            try:
                result = await node.run(state)
                nodes_executed.append(current_node_name)
                state.record_node_output(current_node_name, result.output)

                if self.audit_log:
                    self.audit_log.record(
                        action="workflow_node_completed",
                        actor="system",
                        resource=f"{self.workflow.name}.{current_node_name}",
                        detail={
                            "execution_id": state.execution_id,
                            "success": result.success,
                            "next_nodes": result.next_nodes,
                        },
                    )

                if result.metadata.get("requires_approval"):
                    state.status = ExecutionStatus.PAUSED
                    state.paused_at = datetime.now()
                    state.metadata["awaiting_approval"] = {
                        "node": current_node_name,
                        "timeout_hours": result.metadata.get("timeout_hours"),
                        "escalate_to": result.metadata.get("escalate_to"),
                    }
                    await self.state_store.save(state)

                    return WorkflowExecution(
                        execution_id=state.execution_id,
                        workflow_id=self.workflow.id,
                        workflow_name=self.workflow.name,
                        status=ExecutionStatus.PAUSED,
                        output={"awaiting_approval": True, "node": current_node_name},
                        nodes_executed=nodes_executed,
                        duration_ms=(datetime.now() - start_time).total_seconds() * 1000,
                        started_at=state.started_at,
                        state=state,
                    )

                if result.success:
                    pending_nodes.extend(result.next_nodes)
                else:
                    if result.next_nodes:
                        pending_nodes.extend(result.next_nodes)
                    else:
                        state.record_error(current_node_name, result.error or "Unknown error")
                        state.status = ExecutionStatus.FAILED
                        break

            except Exception as e:
                state.record_error(current_node_name, str(e))
                state.status = ExecutionStatus.FAILED

                if self.audit_log:
                    self.audit_log.record(
                        action="workflow_node_failed",
                        actor="system",
                        resource=f"{self.workflow.name}.{current_node_name}",
                        detail={"execution_id": state.execution_id, "error": str(e)},
                    )
                break

            await self.state_store.save(state)

        if not pending_nodes and state.status == ExecutionStatus.RUNNING:
            state.status = ExecutionStatus.COMPLETED
            state.completed_at = datetime.now()

            if self.audit_log:
                self.audit_log.record(
                    action="workflow_completed",
                    actor="system",
                    resource=self.workflow.name,
                    detail={
                        "execution_id": state.execution_id,
                        "nodes_executed": len(nodes_executed),
                    },
                )

        if state.status == ExecutionStatus.FAILED:
            state.completed_at = datetime.now()

            if self.audit_log:
                self.audit_log.record(
                    action="workflow_failed",
                    actor="system",
                    resource=self.workflow.name,
                    detail={
                        "execution_id": state.execution_id,
                        "errors": state.errors,
                    },
                )

        await self.state_store.save(state)

        if self.metrics:
            self.metrics.counter("auraos_workflow_completed").inc()
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self.metrics.histogram("auraos_workflow_duration_ms").observe(duration)

        return WorkflowExecution(
            execution_id=state.execution_id,
            workflow_id=self.workflow.id,
            workflow_name=self.workflow.name,
            status=state.status,
            output=state.data,
            error=state.errors[-1]["error"] if state.errors else None,
            nodes_executed=nodes_executed,
            duration_ms=(datetime.now() - start_time).total_seconds() * 1000,
            started_at=state.started_at,
            completed_at=state.completed_at,
            state=state,
        )

    async def submit_approval(
        self,
        execution_id: str,
        decision: str,
        approver: str | None = None,
    ) -> WorkflowExecution:
        """Submit an approval decision for a paused workflow."""
        state = await self.state_store.load(execution_id)
        if not state:
            return WorkflowExecution(
                execution_id=execution_id,
                workflow_id="",
                workflow_name="",
                status=ExecutionStatus.FAILED,
                error=f"Execution {execution_id} not found",
            )

        if state.status != ExecutionStatus.PAUSED:
            return WorkflowExecution(
                execution_id=execution_id,
                workflow_id=state.workflow_id,
                workflow_name=state.workflow_name,
                status=state.status,
                error=f"Cannot submit approval: status is {state.status.value}",
            )

        state.set("_approval_submitted", True)
        state.set("approval_decision", decision)
        state.set("approver", approver)
        state.metadata.pop("awaiting_approval", None)

        if self.audit_log:
            self.audit_log.record(
                action="workflow_approval_submitted",
                actor=approver or "system",
                resource=self.workflow.name,
                detail={
                    "execution_id": execution_id,
                    "decision": decision,
                },
            )

        return await self.resume(execution_id)
