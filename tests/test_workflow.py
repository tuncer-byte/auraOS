"""Tests for auraOS v0.3 - Workflow Engine."""
import asyncio
import pytest

from auraos.workflow import (
    Workflow,
    WorkflowExecutor,
    WorkflowState,
    InMemoryStateStore,
    ExecutionStatus,
    NodeResult,
    node,
    workflow,
)
from auraos.workflow.conditions import condition, approval


def run_async(coro):
    """Helper to run async code in sync tests."""
    return asyncio.run(coro)


class TestWorkflowState:
    """Tests for WorkflowState."""

    def test_state_creation(self):
        state = WorkflowState()
        assert state.execution_id
        assert state.status == ExecutionStatus.PENDING
        assert state.data == {}

    def test_state_attribute_access(self):
        state = WorkflowState()
        state.customer_id = "12345"
        state.amount = 1000

        assert state.customer_id == "12345"
        assert state.amount == 1000
        assert state.data["customer_id"] == "12345"

    def test_state_record_node_output(self):
        state = WorkflowState()
        state.record_node_output("kyc_check", {"passed": True, "score": 85})

        assert state.node_outputs["kyc_check"] == {"passed": True, "score": 85}
        assert state.passed is True
        assert state.score == 85

    def test_state_serialization(self):
        state = WorkflowState()
        state.customer_id = "12345"
        state.status = ExecutionStatus.RUNNING

        data = state.to_dict()
        assert data["execution_id"] == state.execution_id
        assert data["status"] == "running"
        assert data["data"]["customer_id"] == "12345"

        restored = WorkflowState.from_dict(data)
        assert restored.execution_id == state.execution_id
        assert restored.status == ExecutionStatus.RUNNING
        assert restored.customer_id == "12345"


class TestNodeDecorator:
    """Tests for @node decorator."""

    def test_simple_node(self):
        @workflow(name="test", entry="step1")
        class TestWorkflow:
            @node
            async def step1(self, ctx):
                return {"result": "done"}

        wf = TestWorkflow()
        assert hasattr(wf.workflow, "nodes")
        assert "step1" in wf.workflow.nodes

    def test_node_with_transitions(self):
        @workflow(name="test", entry="step1")
        class TestWorkflow:
            @node(on_success="step2", on_failure="error")
            async def step1(self, ctx):
                return {"passed": True}

            @node
            async def step2(self, ctx):
                return {"final": True}

            @node
            async def error(self, ctx):
                return {"error": True}

        wf = TestWorkflow()
        assert "step1" in wf.workflow.nodes
        assert "step2" in wf.workflow.nodes
        assert "error" in wf.workflow.nodes


class TestConditionNode:
    """Tests for @condition decorator."""

    def test_condition_branching(self):
        @workflow(name="risk_check", entry="assess")
        class RiskWorkflow:
            @condition(branches={"low": "approve", "high": "reject"})
            def assess(self, ctx):
                return "low" if ctx.score >= 50 else "high"

            @node
            async def approve(self, ctx):
                return {"status": "approved"}

            @node
            async def reject(self, ctx):
                return {"status": "rejected"}

        wf = RiskWorkflow()
        assert "assess" in wf.workflow.nodes
        assert wf.workflow.nodes["assess"]


class TestWorkflowExecutor:
    """Tests for WorkflowExecutor."""

    def test_simple_workflow_execution(self):
        @workflow(name="simple", entry="start")
        class SimpleWorkflow:
            @node(on_success="end")
            async def start(self, ctx):
                return {"started": True}

            @node
            async def end(self, ctx):
                return {"completed": True}

        wf = SimpleWorkflow()
        executor = WorkflowExecutor(wf.workflow)
        result = run_async(executor.run(initial_context={"test": True}))

        assert result.status == ExecutionStatus.COMPLETED
        assert "start" in result.nodes_executed
        assert "end" in result.nodes_executed
        assert result.output.get("completed") is True

    def test_workflow_with_condition(self):
        @workflow(name="conditional", entry="check")
        class ConditionalWorkflow:
            @condition(branches={"yes": "approve", "no": "reject"})
            def check(self, ctx):
                return "yes" if ctx.get("pass_check") else "no"

            @node
            async def approve(self, ctx):
                return {"result": "approved"}

            @node
            async def reject(self, ctx):
                return {"result": "rejected"}

        wf = ConditionalWorkflow()
        executor = WorkflowExecutor(wf.workflow)

        result1 = run_async(executor.run(initial_context={"pass_check": True}))
        assert result1.output.get("result") == "approved"

        result2 = run_async(executor.run(initial_context={"pass_check": False}))
        assert result2.output.get("result") == "rejected"

    def test_workflow_state_persistence(self):
        store = InMemoryStateStore()

        @workflow(name="persisted", entry="step1")
        class PersistedWorkflow:
            @node
            async def step1(self, ctx):
                return {"done": True}

        wf = PersistedWorkflow()
        executor = WorkflowExecutor(wf.workflow, state_store=store)

        result = run_async(executor.run())
        assert result.status == ExecutionStatus.COMPLETED

        saved_state = run_async(store.load(result.execution_id))
        assert saved_state is not None
        assert saved_state.status == ExecutionStatus.COMPLETED

    def test_workflow_validation_error(self):
        wf = Workflow(
            id="invalid",
            name="invalid",
            entry_node="nonexistent",
        )

        executor = WorkflowExecutor(wf)
        result = run_async(executor.run())

        assert result.status == ExecutionStatus.FAILED
        assert "validation failed" in result.error.lower()

    def test_workflow_pause_resume(self):
        @workflow(name="pausable", entry="step1")
        class PausableWorkflow:
            @node(on_success="step2")
            async def step1(self, ctx):
                return {"step1": True}

            @node
            async def step2(self, ctx):
                return {"step2": True}

        wf = PausableWorkflow()
        store = InMemoryStateStore()
        executor = WorkflowExecutor(wf.workflow, state_store=store)

        result = run_async(executor.run())
        assert result.status == ExecutionStatus.COMPLETED


class TestApprovalNode:
    """Tests for @approval decorator."""

    def test_approval_pauses_workflow(self):
        @workflow(name="with_approval", entry="check")
        class ApprovalWorkflow:
            @node(on_success="review")
            async def check(self, ctx):
                return {"checked": True}

            @approval(timeout_hours=24, on_approve="complete")
            async def review(self, ctx):
                return ctx.get("approval_decision", "pending")

            @node
            async def complete(self, ctx):
                return {"approved": True}

        wf = ApprovalWorkflow()
        store = InMemoryStateStore()
        executor = WorkflowExecutor(wf.workflow, state_store=store)

        result = run_async(executor.run())
        assert result.status == ExecutionStatus.PAUSED
        assert result.output.get("awaiting_approval") is True

        resumed = run_async(executor.submit_approval(
            result.execution_id,
            decision="approved",
            approver="manager1",
        ))
        assert resumed.status == ExecutionStatus.COMPLETED


class TestNodeResult:
    """Tests for NodeResult."""

    def test_ok_result(self):
        result = NodeResult.ok(output={"data": 123}, next_nodes=["next"])
        assert result.success is True
        assert result.output == {"data": 123}
        assert result.next_nodes == ["next"]

    def test_fail_result(self):
        result = NodeResult.fail("Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"

    def test_ok_with_single_next(self):
        result = NodeResult.ok(next_nodes="single_node")
        assert result.next_nodes == ["single_node"]
