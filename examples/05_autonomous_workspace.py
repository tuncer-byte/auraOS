"""
05 - AutonomousAgent: workspace içinde dosya üret + analiz et (gerçek Gemini).
"""
import os
import sys

from auraos import AutonomousAgent, Task
from auraos.llm.factory import get_llm


def main():
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        sys.exit("GEMINI_API_KEY (veya GOOGLE_API_KEY) tanımlı değil; örnek atlandı.")

    agent = AutonomousAgent(
        workspace="./_demo_workspace",
        llm=get_llm("gemini/gemini-2.5-flash"),
    )
    resp = agent.run(Task("Bir rapor.md dosyası oluştur ve workspace içeriğini doğrula"))
    print(resp.output)
    print("Workspace:", resp.metadata["workspace"])


if __name__ == "__main__":
    main()
