"""Workflow class and decorator."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Type

from auraos.workflow.node import Node, FunctionNode, NodeConfig


@dataclass
class Workflow:
    """Workflow definition containing nodes and their connections."""
    id: str
    name: str
    nodes: dict[str, Node] = field(default_factory=dict)
    entry_node: str = ""
    version: str = "1.0"
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        """Add a node to the workflow."""
        self.nodes[node.name] = node

    def get_node(self, name: str) -> Node | None:
        """Get a node by name."""
        return self.nodes.get(name)

    def validate(self) -> list[str]:
        """Validate workflow structure. Returns list of errors."""
        errors = []

        if not self.entry_node:
            errors.append("No entry node defined")
        elif self.entry_node not in self.nodes:
            errors.append(f"Entry node '{self.entry_node}' not found in nodes")

        referenced_nodes = set()
        for node in self.nodes.values():
            if node.config:
                if node.config.on_success:
                    if isinstance(node.config.on_success, str):
                        referenced_nodes.add(node.config.on_success)
                    else:
                        referenced_nodes.update(node.config.on_success)
                if node.config.on_failure:
                    referenced_nodes.add(node.config.on_failure)

        missing = referenced_nodes - set(self.nodes.keys())
        for node_name in missing:
            errors.append(f"Referenced node '{node_name}' not found")

        return errors

    def to_dict(self) -> dict:
        """Serialize workflow to dict."""
        return {
            "id": self.id,
            "name": self.name,
            "entry_node": self.entry_node,
            "version": self.version,
            "description": self.description,
            "nodes": list(self.nodes.keys()),
            "metadata": self.metadata,
        }

    @classmethod
    def from_class(cls, workflow_class: Type) -> "Workflow":
        """Build a Workflow from a decorated class."""
        meta = getattr(workflow_class, "__auraos_workflow_meta__", {})

        wf = cls(
            id=meta.get("id", str(uuid.uuid4())[:8]),
            name=meta.get("name", workflow_class.__name__),
            entry_node=meta.get("entry", ""),
            version=meta.get("version", "1.0"),
            description=meta.get("description", workflow_class.__doc__ or ""),
        )

        for attr_name in dir(workflow_class):
            if attr_name.startswith("_"):
                continue
            attr = getattr(workflow_class, attr_name, None)
            if callable(attr) and getattr(attr, "__auraos_node__", False):
                node_name = getattr(attr, "__auraos_node_name__", attr_name)
                config = getattr(attr, "__auraos_node_config__", None)

                def make_executor(method_name):
                    def execute(inst, ctx):
                        return getattr(inst, method_name)(ctx)
                    return execute

                node = FunctionNode(
                    func=make_executor(attr_name),
                    name=node_name,
                    config=config or NodeConfig(),
                )
                wf.add_node(node)

        return wf


def workflow(
    name: str,
    entry: str,
    version: str = "1.0",
    description: str = "",
) -> Callable:
    """Decorator to define a workflow class.

    Usage:
        @workflow(name="loan_approval", entry="kyc_check", version="1.0")
        class LoanApprovalWorkflow:
            @node(on_success="aml_check")
            async def kyc_check(self, ctx):
                ...
    """
    def decorator(cls: Type) -> Type:
        cls.__auraos_workflow__ = True
        cls.__auraos_workflow_meta__ = {
            "name": name,
            "entry": entry,
            "version": version,
            "description": description or cls.__doc__ or "",
            "id": str(uuid.uuid4())[:8],
        }

        original_init = cls.__init__ if hasattr(cls, "__init__") and cls.__init__ is not object.__init__ else None

        def new_init(self, *args, **kwargs):
            if original_init:
                original_init(self, *args, **kwargs)
            self._workflow = _build_workflow_from_instance(self)

        cls.__init__ = new_init

        @property
        def workflow_property(self) -> Workflow:
            return self._workflow

        cls.workflow = workflow_property
        cls.get_workflow = classmethod(lambda c: Workflow.from_class(c))

        return cls

    return decorator


def _build_workflow_from_instance(instance) -> Workflow:
    """Build a Workflow from an instance with bound methods."""
    cls = type(instance)
    meta = getattr(cls, "__auraos_workflow_meta__", {})

    wf = Workflow(
        id=meta.get("id", str(uuid.uuid4())[:8]),
        name=meta.get("name", cls.__name__),
        entry_node=meta.get("entry", ""),
        version=meta.get("version", "1.0"),
        description=meta.get("description", cls.__doc__ or ""),
    )

    for attr_name in dir(instance):
        if attr_name.startswith("_"):
            continue
        attr = getattr(instance, attr_name, None)
        if callable(attr) and getattr(attr, "__auraos_node__", False):
            node_name = getattr(attr, "__auraos_node_name__", attr_name)
            config = getattr(attr, "__auraos_node_config__", None)

            node = FunctionNode(
                func=attr,
                name=node_name,
                config=config or NodeConfig(),
            )
            wf.add_node(node)

    return wf
