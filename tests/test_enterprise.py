"""auraOS v0.2 enterprise modüllerine testler:
audit, structured logger, metrics, cost, circuit breaker, idempotency, RBAC.
"""
from __future__ import annotations
import json
import logging
import time

import pytest

from auraos import (
    Agent,
    AuditLog,
    AuthorizationError,
    CircuitBreaker,
    CircuitOpenError,
    CostTracker,
    IdempotencyStore,
    MetricsRegistry,
    Principal,
    RBACGuard,
    ToolRegistry,
    configure_json_logging,
    get_correlation_id,
    make_idempotency_key,
    new_correlation_id,
    set_principal,
    tool,
)
from auraos.llm.base import LLMResponse  # type-ref only, no mock
from auraos.observability.metrics import Timer
from auraos.observability.structured_logger import JsonFormatter
from tests.conftest import requires_llm


# ---------- Audit log ----------
def test_audit_log_writes_and_chains(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    r1 = log.write(actor="user1", action="login", resource="auth", outcome="ok")
    r2 = log.write(actor="user1", action="transfer", resource="acct:123", outcome="ok",
                   details={"amount": 100})
    assert r1.seq == 1 and r2.seq == 2
    assert r2.prev_hash == r1.hash
    ok, errors = log.verify()
    assert ok and not errors


def test_audit_log_detects_tampering(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.write(actor="u", action="x", resource="r")
    log.write(actor="u", action="y", resource="r")
    raw = path.read_text().splitlines()
    rec = json.loads(raw[0])
    rec["details"] = {"tampered": True}
    raw[0] = json.dumps(rec)
    path.write_text("\n".join(raw) + "\n")
    log2 = AuditLog(path)
    ok, errors = log2.verify()
    assert not ok and errors


def test_audit_log_tail(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    for i in range(5):
        log.write(actor="u", action=f"a{i}", resource="r")
    tail = log.tail(3)
    assert len(tail) == 3 and tail[-1]["action"] == "a4"


# ---------- Structured logger ----------
def test_json_formatter_includes_correlation():
    new_correlation_id()
    fmt = JsonFormatter()
    rec = logging.LogRecord("t", logging.INFO, "f", 1, "merhaba", None, None)
    rec.extra_field = 42
    out = fmt.format(rec)
    data = json.loads(out)
    assert data["msg"] == "merhaba"
    assert data["level"] == "INFO"
    assert "correlation_id" in data
    assert data["extra_field"] == 42


def test_correlation_id_helpers():
    cid = new_correlation_id()
    assert cid == get_correlation_id()


# ---------- Metrics ----------
def test_metrics_counter_and_render():
    reg = MetricsRegistry()
    c = reg.counter("auraos_test_total", "test counter")
    c.inc(labels={"a": "1"})
    c.inc(2.5, labels={"a": "1"})
    c.inc(labels={"a": "2"})
    text = reg.render_prometheus()
    assert "auraos_test_total" in text
    assert 'a="1"' in text and "3.5" in text


def test_metrics_histogram():
    reg = MetricsRegistry()
    h = reg.histogram("auraos_lat_seconds", "lat", buckets=(0.1, 1.0))
    h.observe(0.05)
    h.observe(0.5)
    h.observe(2.0)
    text = reg.render_prometheus()
    assert "auraos_lat_seconds_bucket" in text
    assert "auraos_lat_seconds_count" in text


def test_metrics_timer_records():
    reg = MetricsRegistry()
    h = reg.histogram("auraos_tt", "")
    with Timer(h, labels={"op": "x"}):
        time.sleep(0.005)
    text = reg.render_prometheus()
    assert 'op="x"' in text


# ---------- Cost ----------
def test_cost_tracker_records():
    ct = CostTracker()
    usd = ct.record(model="gpt-4o-mini", input_tokens=1000, output_tokens=500, session_id="s1")
    assert usd > 0
    s = ct.session("s1")
    assert s.input_tokens == 1000 and s.output_tokens == 500
    assert ct.total().calls == 1


def test_cost_tracker_unknown_model_zero():
    ct = CostTracker()
    usd = ct.record(model="xyz/unknown-1.0", input_tokens=100, output_tokens=100)
    assert usd == 0.0


def test_cost_tracker_normalizes_provider_prefix():
    ct = CostTracker()
    usd = ct.record(model="openai/gpt-4o-mini", input_tokens=1000, output_tokens=0)
    assert usd > 0


# ---------- Circuit breaker ----------
def test_circuit_breaker_opens_after_threshold():
    cb = CircuitBreaker(name="t", failure_threshold=3, recovery_seconds=10)

    def boom():
        raise RuntimeError("fail")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            cb.call(boom)
    with pytest.raises(CircuitOpenError):
        cb.call(boom)


def test_circuit_breaker_recovers_to_half_open():
    cb = CircuitBreaker(name="t", failure_threshold=1, recovery_seconds=0.05)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    time.sleep(0.06)
    assert cb.call(lambda: 42) == 42
    assert cb.state.value == "closed"


# ---------- Idempotency ----------
def test_idempotency_store_remember():
    store = IdempotencyStore(default_ttl=60)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return calls["n"]

    key = make_idempotency_key("transfer", {"to": "X", "amt": 100})
    a = store.remember(key, fn)
    b = store.remember(key, fn)
    assert a == 1 and b == 1 and calls["n"] == 1


def test_idempotency_key_deterministic():
    k1 = make_idempotency_key("op", {"a": 1, "b": 2})
    k2 = make_idempotency_key("op", {"b": 2, "a": 1})
    assert k1 == k2


# ---------- RBAC ----------
def test_rbac_blocks_unauthorized():
    @tool(required_roles={"admin"})
    def admin_tool() -> str:
        return "ok"

    reg = ToolRegistry(rbac_guard=RBACGuard())
    reg.register(admin_tool)
    set_principal(Principal(user_id="u1", roles=frozenset({"user"})))
    with pytest.raises(AuthorizationError):
        reg.invoke("admin_tool", {})


def test_rbac_allows_authorized():
    @tool(required_roles={"admin"})
    def admin_tool() -> str:
        return "ok"

    reg = ToolRegistry(rbac_guard=RBACGuard())
    reg.register(admin_tool)
    set_principal(Principal(user_id="u2", roles=frozenset({"admin"})))
    assert reg.invoke("admin_tool", {}) == "ok"


def test_rbac_no_required_roles_passes():
    @tool
    def public_tool() -> str:
        return "ok"

    reg = ToolRegistry(rbac_guard=RBACGuard())
    reg.register(public_tool)
    set_principal(None)
    assert reg.invoke("public_tool", {}) == "ok"


# ---------- Idempotent tool integration ----------
def test_tool_idempotent_caches_result():
    counter = {"n": 0}

    @tool(idempotent=True)
    def transfer(to: str, amount: float) -> dict:
        counter["n"] += 1
        return {"n": counter["n"], "to": to, "amount": amount}

    reg = ToolRegistry(idempotency_store=IdempotencyStore(default_ttl=60))
    reg.register(transfer)
    a = reg.invoke("transfer", {"to": "X", "amount": 100})
    b = reg.invoke("transfer", {"to": "X", "amount": 100})
    c = reg.invoke("transfer", {"to": "Y", "amount": 100})
    assert a == b
    assert a["n"] == 1 and c["n"] == 2 and counter["n"] == 2


# ---------- Agent integration ----------
@tool
def echo(text: str) -> str:
    "Echo."
    return text


@requires_llm
def test_agent_writes_audit(tmp_path, gemini_llm):
    log = AuditLog(tmp_path / "audit.jsonl")
    agent = Agent(
        llm=gemini_llm, model="gemini/gemini-2.5-flash",
        tools=[echo], audit_log=log, actor="alice",
    )
    agent.run("Sadece 'tamam' yaz", session_id="s")
    entries = log.tail(10)
    actions = [e["action"] for e in entries]
    assert "agent.run.start" in actions
    assert "agent.run.end" in actions
    ok, _ = log.verify()
    assert ok


@requires_llm
def test_agent_records_cost(gemini_llm):
    ct = CostTracker()
    agent = Agent(
        model="gemini/gemini-2.5-flash", llm=gemini_llm,
        tools=[echo], cost_tracker=ct,
    )
    agent.run("Sadece 'merhaba' yaz")
    assert ct.total().calls >= 1


@requires_llm
def test_agent_records_metrics(gemini_llm):
    reg = MetricsRegistry()
    agent = Agent(llm=gemini_llm, model="gemini/gemini-2.5-flash", tools=[echo], metrics=reg)
    agent.run("Sadece 'ok' yaz")
    text = reg.render_prometheus()
    assert "auraos_agent_calls_total" in text
    assert "auraos_agent_latency_seconds" in text
