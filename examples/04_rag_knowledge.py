"""
04 - KnowledgeBase ile RAG: politika belgesinden cevap (gerçek Gemini).
"""
import os
import sys

from auraos import Agent, Task, KnowledgeBase


def main():
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        sys.exit("GEMINI_API_KEY (veya GOOGLE_API_KEY) tanımlı değil; örnek atlandı.")

    kb = KnowledgeBase()
    kb.add(
        "Şirket politikası: 10.000 TL üzerindeki tüm müşteri işlemleri "
        "MASAK'a bildirilmelidir. Bireysel müşterilerin günlük transfer "
        "limiti 50.000 TL'dir. Tüzel kişiler için bu limit 500.000 TL'ye "
        "çıkarılabilir."
    )
    kb.add(
        "KYC süreci en geç 24 saat içinde tamamlanmalı. Eksik belge varsa "
        "müşteriye SMS + e-posta hatırlatması gönderilir."
    )

    agent = Agent(name="PolicyBot", model="gemini/gemini-2.5-flash", knowledge=kb)
    resp = agent.run(Task("MASAK bildirim eşiği nedir?"))
    print(resp.output)


if __name__ == "__main__":
    main()
