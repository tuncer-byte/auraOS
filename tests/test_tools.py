"""Tool ve registry testleri."""
from auraos import tool
from auraos.tools.registry import ToolRegistry


@tool
def topla(a: int, b: int) -> int:
    """İki sayıyı topla.

    Args:
        a: ilk
        b: ikinci
    """
    return a + b


def test_tool_decorator_attaches_schema():
    assert topla.__auraos_tool__ is True
    schema = topla.__auraos_schema__
    assert schema.name == "topla"
    assert "a" in schema.parameters["properties"]


def test_registry_invoke():
    r = ToolRegistry()
    r.register(topla)
    assert r.invoke("topla", {"a": 2, "b": 3}) == 5


def test_registry_unknown():
    r = ToolRegistry()
    try:
        r.invoke("yok", {})
    except Exception as e:
        assert "bulunamad" in str(e).lower()
