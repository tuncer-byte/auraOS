"""
Tracer — agent çalışmasının adımlarını yapılandırılmış kayıt eder.
JSONL dosyasına yazar; ileride Langfuse/PromptLayer'a yönlendirilebilir.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class Tracer:
    def __init__(self, agent_name: str, log_dir: str = "./logs"):
        self.agent_name = agent_name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.task_id: Optional[str] = None

    def _file(self) -> Path:
        date = datetime.utcnow().strftime("%Y-%m-%d")
        return self.log_dir / f"{self.agent_name}-{date}.jsonl"

    def _emit(self, event: dict[str, Any]) -> None:
        event["ts"] = datetime.utcnow().isoformat()
        event["agent"] = self.agent_name
        event["task_id"] = self.task_id
        with self._file().open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def start(self, task_id: str, description: str) -> None:
        self.task_id = task_id
        self._emit({"event": "task_start", "description": description})

    def tool_call(self, name: str, args: dict, result: Any) -> None:
        self._emit({
            "event": "tool_call",
            "name": name,
            "args": args,
            "result": str(result)[:500],
        })

    def end(self, output: str, success: bool = True) -> None:
        self._emit({
            "event": "task_end",
            "success": success,
            "output": output[:500],
        })
