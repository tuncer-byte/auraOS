"""Workflow state management."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ExecutionStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowState:
    """Persistent workflow execution context.

    Stores all data accumulated during workflow execution.
    Accessible by nodes via attribute access (ctx.customer_id).
    """
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    workflow_name: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    current_node: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    node_outputs: dict[str, Any] = field(default_factory=dict)
    errors: list[dict] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    paused_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:
        """Allow attribute access to data dict."""
        if name.startswith("_") or name in self.__dataclass_fields__:
            raise AttributeError(name)
        return self.data.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Store non-field attributes in data dict."""
        if name in self.__dataclass_fields__:
            object.__setattr__(self, name, value)
        else:
            self.data[name] = value

    def set(self, key: str, value: Any) -> None:
        """Explicitly set a data value."""
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a data value with default."""
        return self.data.get(key, default)

    def update(self, values: dict[str, Any]) -> None:
        """Merge values into data."""
        self.data.update(values)

    def record_node_output(self, node_id: str, output: Any) -> None:
        """Record output from a node execution."""
        self.node_outputs[node_id] = output
        if isinstance(output, dict):
            self.data.update(output)

    def record_error(self, node_id: str, error: str) -> None:
        """Record an error from node execution."""
        self.errors.append({
            "node_id": node_id,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        })

    def to_dict(self) -> dict:
        """Serialize state to dict."""
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "current_node": self.current_node,
            "data": self.data,
            "node_outputs": self.node_outputs,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "paused_at": self.paused_at.isoformat() if self.paused_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowState":
        """Deserialize state from dict."""
        state = cls(
            execution_id=data["execution_id"],
            workflow_id=data["workflow_id"],
            workflow_name=data["workflow_name"],
            status=ExecutionStatus(data["status"]),
            current_node=data.get("current_node"),
            data=data.get("data", {}),
            node_outputs=data.get("node_outputs", {}),
            errors=data.get("errors", []),
            metadata=data.get("metadata", {}),
        )
        if data.get("started_at"):
            state.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            state.completed_at = datetime.fromisoformat(data["completed_at"])
        if data.get("paused_at"):
            state.paused_at = datetime.fromisoformat(data["paused_at"])
        return state


class StateStore:
    """Abstract base for workflow state persistence."""

    async def save(self, state: WorkflowState) -> None:
        """Persist workflow state."""
        raise NotImplementedError

    async def load(self, execution_id: str) -> WorkflowState | None:
        """Load workflow state by execution ID."""
        raise NotImplementedError

    async def delete(self, execution_id: str) -> None:
        """Delete workflow state."""
        raise NotImplementedError

    async def list_by_status(self, status: ExecutionStatus) -> list[WorkflowState]:
        """List all workflows with given status."""
        raise NotImplementedError


class InMemoryStateStore(StateStore):
    """In-memory state store for development/testing."""

    def __init__(self) -> None:
        self._states: dict[str, WorkflowState] = {}

    async def save(self, state: WorkflowState) -> None:
        self._states[state.execution_id] = state

    async def load(self, execution_id: str) -> WorkflowState | None:
        return self._states.get(execution_id)

    async def delete(self, execution_id: str) -> None:
        self._states.pop(execution_id, None)

    async def list_by_status(self, status: ExecutionStatus) -> list[WorkflowState]:
        return [s for s in self._states.values() if s.status == status]
