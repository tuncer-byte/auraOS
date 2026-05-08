"""
Team — birden fazla agent'ı koordine eder.

Modlar:
  - SEQUENTIAL: agent'lar sırayla çalışır, çıktı bir sonrakine input olur.
  - COORDINATE: agent'lar bir koordinatör tarafından paralel/birlikte yönetilir.
  - ROUTE: gelen göreve göre uygun agent dinamik olarak seçilir.
"""
from __future__ import annotations
from enum import Enum
from typing import Callable, Optional

from auraos.core.agent import Agent
from auraos.core.task import Task
from auraos.core.response import AgentResponse
from auraos.utils.logger import get_logger

logger = get_logger(__name__)


class TeamMode(str, Enum):
    SEQUENTIAL = "sequential"
    COORDINATE = "coordinate"
    ROUTE = "route"


class Team:
    def __init__(
        self,
        agents: list[Agent],
        mode: TeamMode = TeamMode.SEQUENTIAL,
        coordinator: Optional[Agent] = None,
        router: Optional[Callable[[Task, list[Agent]], Agent]] = None,
        name: str = "Team",
    ):
        if not agents:
            raise ValueError("En az bir agent gerekli")
        self.agents = agents
        self.mode = mode
        self.coordinator = coordinator
        self.router = router
        self.name = name

    def run(self, task: Task | str) -> AgentResponse:
        if isinstance(task, str):
            task = Task(description=task)

        if self.mode == TeamMode.SEQUENTIAL:
            return self._run_sequential(task)
        if self.mode == TeamMode.COORDINATE:
            return self._run_coordinate(task)
        if self.mode == TeamMode.ROUTE:
            return self._run_route(task)
        raise ValueError(f"Bilinmeyen mod: {self.mode}")

    def _run_sequential(self, task: Task) -> AgentResponse:
        current_input = task.description
        last_resp: Optional[AgentResponse] = None
        all_calls = []
        for agent in self.agents:
            logger.info(f"[{self.name}] -> {agent.name}")
            resp = agent.run(Task(description=current_input, context=task.context))
            current_input = resp.output
            all_calls.extend(resp.tool_calls)
            last_resp = resp
        assert last_resp is not None
        last_resp.tool_calls = all_calls
        last_resp.metadata["team_mode"] = "sequential"
        last_resp.metadata["chain"] = [a.name for a in self.agents]
        return last_resp

    def _run_coordinate(self, task: Task) -> AgentResponse:
        if not self.coordinator:
            raise ValueError("COORDINATE modu coordinator ister")

        members_brief = "\n".join(
            f"- {a.name}: {a.system_prompt[:80]}..." for a in self.agents
        )
        plan_task = Task(
            description=(
                f"Görev: {task.description}\n\n"
                f"Takım üyeleri:\n{members_brief}\n\n"
                "Her üyeye atanacak alt-görevleri kısa madde madde listele."
            )
        )
        plan = self.coordinator.run(plan_task)

        outputs: list[str] = []
        for agent in self.agents:
            sub = Task(
                description=f"{plan.output}\n\nKendi rolün için aksiyon al.",
                context=task.context,
            )
            r = agent.run(sub)
            outputs.append(f"### {agent.name}\n{r.output}")

        synthesize = Task(
            description=(
                f"Aşağıdaki üye çıktılarını sentezle ve nihai cevabı yaz.\n\n"
                + "\n\n".join(outputs)
            )
        )
        final = self.coordinator.run(synthesize)
        final.metadata["team_mode"] = "coordinate"
        final.metadata["members"] = [a.name for a in self.agents]
        return final

    def _run_route(self, task: Task) -> AgentResponse:
        if self.router:
            chosen = self.router(task, self.agents)
        else:
            chosen = self.agents[0]
        logger.info(f"[{self.name}] route -> {chosen.name}")
        resp = chosen.run(task)
        resp.metadata["team_mode"] = "route"
        resp.metadata["chosen_agent"] = chosen.name
        return resp
