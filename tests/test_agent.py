"""Agent uçtan uca testleri — gerçek Gemini ile (key yoksa skip)."""
from __future__ import annotations

from auraos import Agent, Task, tool
from tests.conftest import requires_llm


@tool
def carp(a: int, b: int) -> int:
    """İki tam sayıyı çarpar.

    Args:
        a: birinci
        b: ikinci
    """
    return a * b


@requires_llm
def test_agent_runs_tool_then_answers(gemini_llm):
    agent = Agent(tools=[carp], llm=gemini_llm, model="gemini/gemini-2.5-flash")
    resp = agent.run(Task("6 ile 7'yi çarp ve sonucu söyle"))
    assert resp.success
    assert "42" in resp.output
    assert any(tc.name == "carp" for tc in resp.tool_calls)


@requires_llm
def test_agent_no_tool_call(gemini_llm):
    agent = Agent(llm=gemini_llm, model="gemini/gemini-2.5-flash")
    resp = agent.run(Task("Sadece 'selam' yaz, başka hiçbir şey yazma."))
    assert resp.success
    assert "selam" in resp.output.lower()
