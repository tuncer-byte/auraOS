"""
Tool şeması — bir Python fonksiyonundan LLM-uyumlu JSON Schema üretir.
"""
from __future__ import annotations
import inspect
import typing
from dataclasses import dataclass, field
from typing import Any, Callable, get_type_hints


_PY_TO_JSON = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


@dataclass
class ToolSchema:
    """OpenAI/Anthropic tool-call uyumlu şema."""
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_openai(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def to_gemini(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def to_groq(self) -> dict:
        return self.to_openai()


def schema_from_function(func: Callable) -> ToolSchema:
    """Bir Python fonksiyonundan tool şeması üret."""
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    doc = inspect.getdoc(func) or ""

    properties: dict[str, dict] = {}
    required: list[str] = []

    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        ptype = hints.get(pname, str)
        json_type = _PY_TO_JSON.get(ptype, "string")
        properties[pname] = {
            "type": json_type,
            "description": _extract_param_doc(doc, pname),
        }
        if param.default is inspect.Parameter.empty:
            required.append(pname)

    parameters = {
        "type": "object",
        "properties": properties,
        "required": required,
    }

    description = doc.split("\n\n")[0] if doc else func.__name__

    return ToolSchema(
        name=func.__name__,
        description=description.strip(),
        parameters=parameters,
    )


def _extract_param_doc(doc: str, pname: str) -> str:
    for line in doc.splitlines():
        s = line.strip()
        if s.startswith(f"{pname}:") or s.startswith(f"{pname} -"):
            return s.split(":", 1)[-1].split("-", 1)[-1].strip()
    return ""
