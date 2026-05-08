"""
AutonomousAgent — kendi kendine plan yapan, çok adımlı, sandbox tabanlı agent.

Geleneksel Agent tool kataloğuyla sınırlıdır; AutonomousAgent ek olarak
filesystem ve shell yetkisine sahiptir ve workspace içinde reasoning →
plan → execute → reflect döngüsünü kendi yürütür.
"""
from __future__ import annotations
import time
from pathlib import Path
from typing import Optional

from auraos.core.agent import Agent
from auraos.core.task import Task
from auraos.core.response import AgentResponse
from auraos.sandbox.workspace import Workspace
from auraos.sandbox.shell import SafeShell
from auraos.tools.registry import ToolRegistry
from auraos.tools.builtins import file_tools, shell_tools
from auraos.utils.logger import get_logger

logger = get_logger(__name__)


class AutonomousAgent(Agent):
    """
    Otonom agent — kullanıcıdan minimum yönlendirmeyle, sandbox'lanmış
    bir workspace içinde planlama ve yürütme yapar.

    Args:
        workspace: Tüm dosya/komut işlemlerinin sınırlandığı dizin.
        max_iterations: Reasoning döngüsünün üst sınırı.
        require_approval_for: Hangi araç adlarında insan onayı zorunlu.
    """

    def __init__(
        self,
        name: str = "AutonomousAgent",
        model: str = "anthropic/claude-sonnet-4-5",
        workspace: str | Path = "./workspace",
        max_iterations: int = 25,
        require_approval_for: Optional[list[str]] = None,
        **kwargs,
    ):
        self.workspace = Workspace(workspace)
        self.shell = SafeShell(self.workspace)
        self.require_approval_for = set(require_approval_for or [])

        registry = kwargs.pop("tools", None)
        if not isinstance(registry, ToolRegistry):
            registry = ToolRegistry()
            for t in (registry or []) if registry else []:
                registry.register(t)
        for t in file_tools(self.workspace):
            registry.register(t)
        for t in shell_tools(self.shell):
            registry.register(t)

        system_prompt = kwargs.pop("system_prompt", None) or self._autonomous_prompt(workspace)

        super().__init__(
            name=name,
            model=model,
            tools=registry,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            **kwargs,
        )

    def _autonomous_prompt(self, workspace: str | Path) -> str:
        return (
            f"Sen {self.__class__.__name__} adlı otonom bir finansal ajanısın.\n"
            f"WORKSPACE: {workspace}\n"
            "- Tüm dosya ve komut işlemleri yalnızca bu dizinle sınırlıdır.\n"
            "- Path traversal ve tehlikeli komutlar bloklanır.\n"
            "- Önce bir plan yap, sonra her adımı küçük tool çağrılarıyla yürüt.\n"
            "- Her adım sonrası kendini kontrol et (reflect).\n"
            "- Belirsizlikte tool ile veri topla, asla halüsinasyon yapma.\n"
            "- Görev tamamlandığında özet rapor üret."
        )

    def run(self, task: Task | str) -> AgentResponse:
        if isinstance(task, str):
            task = Task(description=task, max_iterations=self.max_iterations)

        logger.info(f"[{self.name}] otonom çalışma başlıyor: {task.description}")
        t0 = time.time()
        response = super().run(task)
        response.metadata["workspace"] = str(self.workspace.root)
        response.metadata["autonomous"] = True
        logger.info(f"[{self.name}] tamamlandı ({(time.time()-t0):.1f}s)")
        return response
