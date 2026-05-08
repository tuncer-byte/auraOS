"""
Agent — geleneksel (tool-driven) agent.

Yetenekler:
  - run() / arun() — sync ve async
  - stream() / astream() — token-by-token streaming
  - Session memory entegrasyonu (session_id ile çağrılabilir)
  - Guardrails (input/output)
  - Rate limiting + cache hook
  - Custom exception hierarchy
"""
from __future__ import annotations
import asyncio
import json
import time
from typing import Any, AsyncIterator, Callable, Iterator, Optional

from auraos.core.task import Task
from auraos.core.response import AgentResponse, ToolCall
from auraos.exceptions import (
    AuraOSError,
    LLMError,
    MaxIterationsExceeded,
    ToolApprovalRequired,
    ToolError,
)
from auraos.guardrails import Guardrails
from auraos.knowledge.base import KnowledgeBase
from auraos.llm.base import BaseLLM, StreamChunk
from auraos.llm.factory import get_llm
from auraos.memory.base import Memory
from auraos.memory.session import Session, SessionManager
from auraos.observability.audit import AuditLog
from auraos.observability.cost import CostTracker
from auraos.observability.metrics import METRICS, MetricsRegistry, Timer
from auraos.observability.structured_logger import (
    get_correlation_id,
    new_correlation_id,
    set_session_id,
)
from auraos.observability.tracer import Tracer
from auraos.tools.registry import ApprovalCallback, ToolRegistry
from auraos.utils.cache import InMemoryCache, make_cache_key
from auraos.utils.circuit_breaker import CircuitBreaker, CircuitOpenError
from auraos.utils.logger import get_logger
from auraos.utils.rate_limit import RateLimiter

logger = get_logger(__name__)


class Agent:
    def __init__(
        self,
        name: str = "Agent",
        model: str = "anthropic/claude-sonnet-4-5",
        tools: Optional[list[Callable] | ToolRegistry] = None,
        memory: Optional[Memory] = None,
        knowledge: Optional[KnowledgeBase] = None,
        system_prompt: Optional[str] = None,
        max_iterations: int = 10,
        llm: Optional[BaseLLM] = None,
        session_manager: Optional[SessionManager] = None,
        guardrails: Optional[Guardrails] = None,
        rate_limiter: Optional[RateLimiter] = None,
        rate_limit_scope: Optional[str] = None,
        cache: Optional[InMemoryCache] = None,
        cache_llm_responses: bool = False,
        approval_callback: Optional[ApprovalCallback] = None,
        tool_timeout: Optional[float] = None,
        audit_log: Optional[AuditLog] = None,
        cost_tracker: Optional[CostTracker] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        metrics: Optional[MetricsRegistry] = None,
        actor: Optional[str] = None,
    ):
        self.name = name
        self.model = model
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.max_iterations = max_iterations
        self.memory = memory
        self.knowledge = knowledge
        self.tracer = Tracer(agent_name=name)

        if isinstance(tools, ToolRegistry):
            self.registry = tools
            if approval_callback and self.registry.approval_callback is None:
                self.registry.approval_callback = approval_callback
            if tool_timeout is not None and self.registry.default_timeout is None:
                self.registry.default_timeout = tool_timeout
        else:
            self.registry = ToolRegistry(approval_callback=approval_callback, default_timeout=tool_timeout)
            for t in tools or []:
                self.registry.register(t)

        self.llm = llm or get_llm(model)
        self.session_manager = session_manager
        self.guardrails = guardrails
        self.rate_limiter = rate_limiter
        self.rate_limit_scope = rate_limit_scope
        self.cache = cache
        self.cache_llm_responses = cache_llm_responses
        self.audit_log = audit_log
        self.cost_tracker = cost_tracker
        self.circuit_breaker = circuit_breaker
        self.metrics = metrics or METRICS
        self.actor = actor or name

        self._m_calls = self.metrics.counter("auraos_agent_calls_total", "Agent çağrı sayısı")
        self._m_errors = self.metrics.counter("auraos_agent_errors_total", "Agent hata sayısı")
        self._m_iter = self.metrics.histogram("auraos_agent_iterations", "Iteration sayısı dağılımı", buckets=(1, 2, 3, 5, 8, 13))
        self._m_latency = self.metrics.histogram("auraos_agent_latency_seconds", "Agent çağrı süresi")
        self._m_tool_calls = self.metrics.counter("auraos_tool_calls_total", "Tool çağrı sayısı")
        self._m_tool_latency = self.metrics.histogram("auraos_tool_latency_seconds", "Tool süresi")
        self._m_llm_tokens = self.metrics.counter("auraos_llm_tokens_total", "LLM token kullanımı")
        self._m_llm_cost = self.metrics.counter("auraos_llm_cost_usd_total", "LLM USD maliyeti")

    def _default_system_prompt(self) -> str:
        return (
            f"Sen {self.name} adlı yardımcı bir finansal AI ajanısın. "
            "Sana verilen tool'ları kullanarak görevi yerine getir. "
            "Cevaplarında net, kısa ve güvenilir ol. "
            "Bilmediğin bir şeyi tahmin etme; tool'lardan veri çek."
        )

    # ---------- Mesaj inşası ----------
    def _build_messages(
        self,
        task_text: str,
        session: Optional[Session] = None,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        if self.knowledge:
            ctx = self.knowledge.search(task_text, top_k=3)
            if ctx:
                messages.append({"role": "system", "content": f"İlgili bilgi tabanı verisi:\n{ctx}"})
        if session:
            messages.extend(session.recent(limit=20))
        elif self.memory:
            messages.extend(self.memory.get_recent(limit=10))
        messages.append({"role": "user", "content": task_text})
        return messages

    def _resolve_session(self, session_id: Optional[str]) -> Optional[Session]:
        if session_id is None or self.session_manager is None:
            return None
        return self.session_manager.get_or_create(session_id)

    def _ensure_correlation(self, session_id: Optional[str]) -> str:
        cid = get_correlation_id() or new_correlation_id()
        if session_id:
            set_session_id(session_id)
        return cid

    def _audit(self, action: str, outcome: str, *, session_id: Optional[str], details: dict | None = None) -> None:
        if self.audit_log is None:
            return
        try:
            self.audit_log.write(
                actor=self.actor,
                action=action,
                resource=f"agent:{self.name}",
                outcome=outcome,
                correlation_id=get_correlation_id(),
                session_id=session_id,
                details=details or {},
            )
        except Exception as e:
            logger.warning("audit write failed: %s", e)

    def _record_llm_metrics(self, resp, session_id: Optional[str]) -> None:
        tokens = getattr(resp, "tokens_used", 0) or 0
        if tokens:
            self._m_llm_tokens.inc(tokens, labels={"model": self.model, "agent": self.name})
        if self.cost_tracker:
            ip = getattr(resp, "input_tokens", None)
            op = getattr(resp, "output_tokens", None)
            if ip is None or op is None:
                ip, op = max(0, int(tokens * 0.6)), max(0, tokens - int(tokens * 0.6))
            usd = self.cost_tracker.record(
                model=self.model, input_tokens=ip, output_tokens=op, session_id=session_id
            )
            self._m_llm_cost.inc(usd, labels={"model": self.model})

    # ---------- Sync run ----------
    def run(
        self,
        task: Task | str,
        session_id: Optional[str] = None,
    ) -> AgentResponse:
        if isinstance(task, str):
            task = Task(description=task)

        cid = self._ensure_correlation(session_id)
        start = time.time()
        self.tracer.start(task.task_id, task.description)
        self._m_calls.inc(labels={"agent": self.name})
        self._audit("agent.run.start", "ok", session_id=session_id, details={"task_id": task.task_id, "correlation_id": cid})

        if self.guardrails:
            inp = self.guardrails.check_input(task.description)
            if not inp.ok and self.guardrails.raise_on_violation:
                self._audit("agent.run.input_blocked", "denied", session_id=session_id, details={"hits": inp.hits})
                raise AuraOSError("Input guardrail violation", details={"hits": inp.hits})

        session = self._resolve_session(session_id)
        messages = self._build_messages(task.description, session=session)

        tool_calls: list[ToolCall] = []
        total_tokens = 0
        iteration = 0
        final_output = ""

        try:
            for iteration in range(1, self.max_iterations + 1):
                logger.info(f"[{self.name}] iter={iteration}")
                if self.rate_limiter and self.rate_limit_scope:
                    self.rate_limiter.acquire(self.rate_limit_scope)

                llm_resp = self._call_llm(messages)
                total_tokens += llm_resp.tokens_used

                if llm_resp.tool_calls:
                    for tc in llm_resp.tool_calls:
                        call = self._invoke_tool_sync(tc)
                        tool_calls.append(call)
                        messages.append({"role": "assistant", "content": None, "tool_calls": [tc]})
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", tc["name"]),
                            "content": json.dumps(call.result, default=str),
                        })
                else:
                    final_output = llm_resp.content
                    break
            else:
                raise MaxIterationsExceeded(
                    f"Agent {self.name} reached max_iterations={self.max_iterations}"
                )

            if self.guardrails:
                out = self.guardrails.check_output(final_output)
                final_output = out.text

            self._persist_turn(session, task.description, final_output)
            self.tracer.end(final_output, success=True)
            success = True
            error_msg = None

        except AuraOSError as e:
            logger.error(f"[{self.name}] aborted: {e}", exc_info=True)
            self.tracer.end(str(e), success=False)
            self._m_errors.inc(labels={"agent": self.name, "error": e.__class__.__name__})
            self._audit("agent.run.error", "error", session_id=session_id, details={"error": str(e), "type": e.__class__.__name__})
            final_output = f"Hata: {e.message}"
            success = False
            error_msg = e.message

        duration_ms = (time.time() - start) * 1000
        self._m_iter.observe(iteration, labels={"agent": self.name})
        self._m_latency.observe(duration_ms / 1000.0, labels={"agent": self.name})
        if success:
            self._audit("agent.run.end", "ok", session_id=session_id, details={"iterations": iteration, "tokens": total_tokens, "duration_ms": int(duration_ms)})
        return AgentResponse(
            output=final_output,
            success=success,
            tool_calls=tool_calls,
            iterations=iteration,
            tokens_used=total_tokens,
            duration_ms=duration_ms,
            error=error_msg,
        )

    # ---------- Async run ----------
    async def arun(
        self,
        task: Task | str,
        session_id: Optional[str] = None,
    ) -> AgentResponse:
        if isinstance(task, str):
            task = Task(description=task)

        cid = self._ensure_correlation(session_id)
        start = time.time()
        self.tracer.start(task.task_id, task.description)
        self._m_calls.inc(labels={"agent": self.name})
        self._audit("agent.arun.start", "ok", session_id=session_id, details={"task_id": task.task_id, "correlation_id": cid})

        if self.guardrails:
            inp = self.guardrails.check_input(task.description)
            if not inp.ok and self.guardrails.raise_on_violation:
                self._audit("agent.arun.input_blocked", "denied", session_id=session_id, details={"hits": inp.hits})
                raise AuraOSError("Input guardrail violation", details={"hits": inp.hits})

        session = self._resolve_session(session_id)
        messages = self._build_messages(task.description, session=session)

        tool_calls: list[ToolCall] = []
        total_tokens = 0
        iteration = 0
        final_output = ""

        try:
            for iteration in range(1, self.max_iterations + 1):
                if self.rate_limiter and self.rate_limit_scope:
                    await self.rate_limiter.aacquire(self.rate_limit_scope)

                llm_resp = await self._acall_llm(messages)
                total_tokens += llm_resp.tokens_used

                if llm_resp.tool_calls:
                    for tc in llm_resp.tool_calls:
                        call = await self._invoke_tool_async(tc)
                        tool_calls.append(call)
                        messages.append({"role": "assistant", "content": None, "tool_calls": [tc]})
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", tc["name"]),
                            "content": json.dumps(call.result, default=str),
                        })
                else:
                    final_output = llm_resp.content
                    break
            else:
                raise MaxIterationsExceeded(
                    f"Agent {self.name} reached max_iterations={self.max_iterations}"
                )

            if self.guardrails:
                out = self.guardrails.check_output(final_output)
                final_output = out.text

            self._persist_turn(session, task.description, final_output)
            self.tracer.end(final_output, success=True)
            success = True
            error_msg = None

        except AuraOSError as e:
            logger.error(f"[{self.name}] aborted: {e}", exc_info=True)
            self.tracer.end(str(e), success=False)
            self._m_errors.inc(labels={"agent": self.name, "error": e.__class__.__name__})
            self._audit("agent.arun.error", "error", session_id=session_id, details={"error": str(e), "type": e.__class__.__name__})
            final_output = f"Hata: {e.message}"
            success = False
            error_msg = e.message

        duration_ms = (time.time() - start) * 1000
        self._m_iter.observe(iteration, labels={"agent": self.name})
        self._m_latency.observe(duration_ms / 1000.0, labels={"agent": self.name})
        if success:
            self._audit("agent.arun.end", "ok", session_id=session_id, details={"iterations": iteration, "tokens": total_tokens, "duration_ms": int(duration_ms)})
        return AgentResponse(
            output=final_output,
            success=success,
            tool_calls=tool_calls,
            iterations=iteration,
            tokens_used=total_tokens,
            duration_ms=duration_ms,
            error=error_msg,
        )

    # ---------- Streaming ----------
    async def astream(
        self,
        task: Task | str,
        session_id: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Token-by-token streaming. Tool çağrıları geldiğinde tool çalışıp
        bir sonraki LLM turuna geçilir; her chunk yield edilir.
        """
        if isinstance(task, str):
            task = Task(description=task)

        if self.guardrails:
            inp = self.guardrails.check_input(task.description)
            if not inp.ok and self.guardrails.raise_on_violation:
                raise AuraOSError("Input guardrail violation", details={"hits": inp.hits})

        session = self._resolve_session(session_id)
        messages = self._build_messages(task.description, session=session)

        accumulated_text = ""
        for iteration in range(1, self.max_iterations + 1):
            if self.rate_limiter and self.rate_limit_scope:
                await self.rate_limiter.aacquire(self.rate_limit_scope)

            iter_text = ""
            iter_tool_calls: list[dict[str, Any]] = []

            async for chunk in self.llm.astream(
                messages=messages,
                tools=self.registry.schemas(),
            ):
                if chunk.type == "text":
                    iter_text += chunk.text
                    accumulated_text += chunk.text
                    yield chunk
                elif chunk.type == "tool_call":
                    iter_tool_calls.append(chunk.tool_call)
                    yield chunk
                elif chunk.type == "error":
                    yield chunk
                    return
                elif chunk.type == "done":
                    pass  # iter sonunda doğal akış

            if iter_tool_calls:
                for tc in iter_tool_calls:
                    call = await self._invoke_tool_async(tc)
                    yield StreamChunk(
                        type="tool_call",
                        tool_call={**tc, "result": call.result},
                    )
                    messages.append({"role": "assistant", "content": iter_text or None, "tool_calls": [tc]})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", tc["name"]),
                        "content": json.dumps(call.result, default=str),
                    })
                continue
            break

        if self.guardrails:
            out = self.guardrails.check_output(accumulated_text)
            if not out.ok:
                yield StreamChunk(type="text", text=f"\n\n[guardrail: {out.reason}]")
                accumulated_text = out.text

        self._persist_turn(session, task.description, accumulated_text)
        yield StreamChunk(type="done")

    # ---------- Yardımcı: LLM çağrısı (cache + error wrap) ----------
    def _call_llm(self, messages: list[dict[str, Any]]):
        if self.cache_llm_responses and self.cache:
            key = make_cache_key("llm", self.model, messages, self.registry.names())
            cached = self.cache.get(key)
            if cached is not None:
                return cached
        try:
            if self.circuit_breaker:
                resp = self.circuit_breaker.call(
                    self.llm.complete, messages=messages, tools=self.registry.schemas()
                )
            else:
                resp = self.llm.complete(messages=messages, tools=self.registry.schemas())
        except CircuitOpenError:
            self._m_errors.inc(labels={"agent": self.name, "error": "CircuitOpen"})
            raise LLMError("LLM circuit open", details={"breaker": self.circuit_breaker.name if self.circuit_breaker else ""})
        except AuraOSError:
            raise
        except Exception as e:
            raise LLMError(f"LLM call failed: {e}") from e
        self._record_llm_metrics(resp, session_id=None)
        if self.cache_llm_responses and self.cache and not resp.tool_calls:
            self.cache.set(key, resp)
        return resp

    async def _acall_llm(self, messages: list[dict[str, Any]]):
        try:
            if self.circuit_breaker:
                resp = await self.circuit_breaker.acall(
                    self.llm.acomplete, messages=messages, tools=self.registry.schemas()
                )
            else:
                resp = await self.llm.acomplete(messages=messages, tools=self.registry.schemas())
        except CircuitOpenError:
            self._m_errors.inc(labels={"agent": self.name, "error": "CircuitOpen"})
            raise LLMError("LLM circuit open")
        except AuraOSError:
            raise
        except Exception as e:
            raise LLMError(f"LLM call failed: {e}") from e
        self._record_llm_metrics(resp, session_id=None)
        return resp

    def _invoke_tool_sync(self, tc: dict[str, Any]) -> ToolCall:
        t0 = time.time()
        outcome = "ok"
        try:
            with Timer(self._m_tool_latency, labels={"tool": tc["name"]}):
                result = self.registry.invoke(tc["name"], tc.get("arguments", {}))
        except ToolApprovalRequired as e:
            outcome = "denied"
            result = {"error": "approval_required", "message": e.message, "arguments": e.arguments}
        except ToolError as e:
            outcome = "error"
            result = e.to_dict()
        except Exception as e:
            outcome = "error"
            result = {"error": "unexpected", "message": str(e)}
        duration = (time.time() - t0) * 1000
        self._m_tool_calls.inc(labels={"tool": tc["name"], "outcome": outcome})
        call = ToolCall(name=tc["name"], arguments=tc.get("arguments", {}), result=result, duration_ms=duration)
        self.tracer.tool_call(tc["name"], tc.get("arguments", {}), result)
        if self.audit_log:
            self._audit(
                f"tool.invoke:{tc['name']}", outcome,
                session_id=None,
                details={"args": tc.get("arguments", {}), "duration_ms": int(duration)},
            )
        return call

    async def _invoke_tool_async(self, tc: dict[str, Any]) -> ToolCall:
        t0 = time.time()
        outcome = "ok"
        try:
            with Timer(self._m_tool_latency, labels={"tool": tc["name"]}):
                result = await self.registry.ainvoke(tc["name"], tc.get("arguments", {}))
        except ToolApprovalRequired as e:
            outcome = "denied"
            result = {"error": "approval_required", "message": e.message, "arguments": e.arguments}
        except ToolError as e:
            outcome = "error"
            result = e.to_dict()
        except Exception as e:
            outcome = "error"
            result = {"error": "unexpected", "message": str(e)}
        duration = (time.time() - t0) * 1000
        self._m_tool_calls.inc(labels={"tool": tc["name"], "outcome": outcome})
        call = ToolCall(name=tc["name"], arguments=tc.get("arguments", {}), result=result, duration_ms=duration)
        self.tracer.tool_call(tc["name"], tc.get("arguments", {}), result)
        if self.audit_log:
            self._audit(
                f"tool.invoke:{tc['name']}", outcome,
                session_id=None,
                details={"args": tc.get("arguments", {}), "duration_ms": int(duration)},
            )
        return call

    def _persist_turn(self, session: Optional[Session], user_msg: str, assistant_msg: str) -> None:
        if session is not None and self.session_manager is not None:
            session.add_message("user", user_msg)
            session.add_message("assistant", assistant_msg)
            self.session_manager.save(session)
        if self.memory is not None:
            self.memory.add({"role": "user", "content": user_msg})
            self.memory.add({"role": "assistant", "content": assistant_msg})

    def __repr__(self) -> str:
        return f"Agent(name={self.name!r}, model={self.model!r}, tools={len(self.registry)})"
