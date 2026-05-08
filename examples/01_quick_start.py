"""
01 - Hızlı başlangıç: özel tool'la bir Agent çalıştır.

GERÇEK Gemini provider kullanılır. Çalıştırmak için:
    export GEMINI_API_KEY=...
    python examples/01_quick_start.py
"""
import os
import sys

from auraos import Agent, Task, tool


@tool
def topla(a: int, b: int) -> int:
    """İki tamsayıyı toplar.

    Args:
        a: İlk sayı
        b: İkinci sayı
    """
    return a + b


def main():
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        sys.exit("GEMINI_API_KEY (veya GOOGLE_API_KEY) tanımlı değil; örnek atlandı.")

    agent = Agent(name="Hesapçı", model="gemini/gemini-2.5-flash", tools=[topla])
    resp = agent.run(Task("5 ile 7'yi topla ve sonucu söyle"))

    print("Çıktı:", resp.output)
    print("Tool çağrıları:", [(c.name, c.result) for c in resp.tool_calls])
    print("İterasyon:", resp.iterations)


if __name__ == "__main__":
    main()
