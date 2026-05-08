"""Sub-agent tool factory for spawning agents as tools."""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TYPE_CHECKING

from auraos.tools.decorator import tool

if TYPE_CHECKING:
    from auraos.core.agent import Agent


def create_sub_agent_tool(
    agent: "Agent",
    name: str | None = None,
    description: str | None = None,
    pass_context: bool = False,
) -> Callable:
    """Create a tool that runs a sub-agent.

    This allows agents to spawn other specialized agents as tools,
    enabling hierarchical agent architectures.

    Args:
        agent: The agent to wrap as a tool
        name: Tool name (default: sub_{agent.name})
        description: Tool description (default: auto-generated)
        pass_context: If True, passes context data to sub-agent

    Returns:
        A tool function that runs the sub-agent

    Usage:
        kyc_agent = OnboardingAgent()
        aml_agent = AMLAgent()

        main_agent = Agent(
            tools=[
                create_sub_agent_tool(kyc_agent, name="run_kyc"),
                create_sub_agent_tool(aml_agent, name="run_aml"),
            ]
        )
    """
    tool_name = name or f"sub_{agent.name.lower().replace(' ', '_')}"
    tool_description = description or f"Run {agent.name} sub-agent to process a query."

    @tool(name=tool_name, description=tool_description, requires_approval=False)
    async def run_sub_agent(query: str, context: dict | None = None) -> dict:
        """Run the sub-agent with the given query.

        Args:
            query: The query/task to send to the sub-agent
            context: Optional context data to include

        Returns:
            dict with success, output, and tool_calls
        """
        from auraos.core.task import Task

        task_description = query
        if pass_context and context:
            task_description = f"{query}\n\nContext: {context}"

        result = await agent.arun(Task(description=task_description))

        return {
            "success": result.success,
            "output": result.output,
            "tool_calls": [tc.name for tc in result.tool_calls],
            "iterations": result.iterations,
            "error": result.error,
        }

    run_sub_agent.__auraos_sub_agent__ = True
    run_sub_agent.__auraos_sub_agent_name__ = agent.name
    return run_sub_agent


def create_agent_router(
    agents: dict[str, "Agent"],
    name: str = "route_to_agent",
    description: str | None = None,
) -> Callable:
    """Create a router tool that dispatches to multiple agents.

    Args:
        agents: Mapping of agent names to agent instances
        name: Tool name
        description: Tool description

    Returns:
        A tool that routes queries to the appropriate agent

    Usage:
        router = create_agent_router({
            "kyc": OnboardingAgent(),
            "aml": AMLAgent(),
            "credit": CreditAgent(),
        })

        main_agent = Agent(tools=[router])
    """
    agent_list = ", ".join(agents.keys())
    tool_description = description or f"Route query to a specialized agent. Available: {agent_list}"

    @tool(name=name, description=tool_description, requires_approval=False)
    async def route_to_agent(agent_name: str, query: str) -> dict:
        """Route a query to a specialized agent.

        Args:
            agent_name: Name of the agent to route to
            query: The query/task to send

        Returns:
            dict with agent result
        """
        from auraos.core.task import Task

        if agent_name not in agents:
            return {
                "success": False,
                "error": f"Agent '{agent_name}' not found. Available: {agent_list}",
            }

        agent = agents[agent_name]
        result = await agent.arun(Task(description=query))

        return {
            "agent": agent_name,
            "success": result.success,
            "output": result.output,
            "tool_calls": [tc.name for tc in result.tool_calls],
            "error": result.error,
        }

    route_to_agent.__auraos_agent_router__ = True
    route_to_agent.__auraos_routed_agents__ = list(agents.keys())
    return route_to_agent
