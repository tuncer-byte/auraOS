"""
Tool çağrılarını parametrelerin imzasına göre validate eder.

Pydantic varsa kullanır (richer types), yoksa standart kütüphane ile
çalışan light validator devreye girer (type coercion + required check).
"""
from __future__ import annotations
import inspect
from typing import Any, Callable, get_type_hints

from auraos.exceptions import ToolValidationError

try:
    from pydantic import TypeAdapter, ValidationError  # type: ignore
    _PYDANTIC = True
except ImportError:
    _PYDANTIC = False


def _coerce(value: Any, target: type) -> Any:
    if value is None or target is type(None):
        return value
    if target in (Any, inspect.Parameter.empty):
        return value
    if isinstance(value, target):
        return value
    try:
        if target is bool:
            if isinstance(value, str):
                return value.strip().lower() in {"true", "1", "yes", "evet"}
            return bool(value)
        if target in (int, float, str):
            return target(value)
    except (TypeError, ValueError) as e:
        raise ToolValidationError("?", f"cannot coerce {value!r} to {target.__name__}: {e}")
    return value


def validate_tool_arguments(func: Callable, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Çağrılmadan önce argümanları imzaya göre validate et + tip dönüşümü.

    Pydantic varsa TypeAdapter ile validate eder (annotated constraints
    çalışır). Yoksa minimum: required check + basit coerce.
    """
    sig = inspect.signature(func)
    hints = get_type_hints(func, include_extras=True)
    cleaned: dict[str, Any] = {}

    # Bilinmeyen anahtarları at (LLM bazen ekstra alan üretir)
    accepted = {p.name for p in sig.parameters.values()}

    has_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD
        for p in sig.parameters.values()
    )
    if has_var_keyword:
        return dict(arguments)

    for key in list(arguments.keys()):
        if key not in accepted:
            arguments.pop(key, None)

    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        provided = pname in arguments
        if not provided:
            if param.default is inspect.Parameter.empty:
                raise ToolValidationError(tool_name, f"missing required parameter: {pname}")
            continue

        value = arguments[pname]
        annotation = hints.get(pname, param.annotation)

        if _PYDANTIC and annotation not in (inspect.Parameter.empty, None):
            try:
                value = TypeAdapter(annotation).validate_python(value)
            except ValidationError as e:
                raise ToolValidationError(tool_name, f"invalid value for {pname}: {e.errors()[0]['msg']}")
        elif annotation not in (inspect.Parameter.empty, None) and isinstance(annotation, type):
            try:
                value = _coerce(value, annotation)
            except ToolValidationError as e:
                raise ToolValidationError(tool_name, f"{pname}: {e.message}")

        cleaned[pname] = value

    return cleaned
