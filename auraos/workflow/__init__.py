"""auraOS Workflow Engine.

Enables building complex banking workflows as Python DSL.

Example:
    from auraos.workflow import workflow, node, WorkflowExecutor
    from auraos.workflow.conditions import condition, approval

    @workflow(name="loan_approval", entry="kyc_check")
    class LoanApprovalWorkflow:

        @node(on_success="risk_check")
        async def kyc_check(self, ctx):
            return {"kyc_passed": True}

        @condition(branches={"low": "approve", "high": "reject"})
        def risk_check(self, ctx):
            return "low" if ctx.kyc_passed else "high"

        @node
        async def approve(self, ctx):
            return {"status": "approved"}

        @node
        async def reject(self, ctx):
            return {"status": "rejected"}

    # Execute
    wf = LoanApprovalWorkflow()
    executor = WorkflowExecutor(wf.workflow)
    result = await executor.run(initial_context={"customer_id": "12345"})
"""
from auraos.workflow.node import Node, NodeResult, NodeConfig, FunctionNode, node
from auraos.workflow.workflow import Workflow, workflow
from auraos.workflow.executor import WorkflowExecutor, WorkflowExecution
from auraos.workflow.state import (
    WorkflowState,
    StateStore,
    InMemoryStateStore,
    ExecutionStatus,
)
from auraos.workflow.conditions import condition, approval, parallel, merge

__all__ = [
    "Node",
    "NodeResult",
    "NodeConfig",
    "FunctionNode",
    "node",
    "Workflow",
    "workflow",
    "WorkflowExecutor",
    "WorkflowExecution",
    "WorkflowState",
    "StateStore",
    "InMemoryStateStore",
    "ExecutionStatus",
    "condition",
    "approval",
    "parallel",
    "merge",
]
