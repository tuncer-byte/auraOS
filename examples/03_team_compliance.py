"""
03 - Multi-agent: Onboarding -> AML -> rapor zinciri (gerçek Gemini ile).
"""
import os
import sys

from auraos import Team, TeamMode, Task
from auraos.fintech import OnboardingAgent, AMLAgent
from auraos.llm.factory import get_llm


def main():
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        sys.exit("GEMINI_API_KEY (veya GOOGLE_API_KEY) tanımlı değil; örnek atlandı.")

    llm = get_llm("gemini/gemini-2.5-flash")
    onboarding = OnboardingAgent(llm=llm)
    aml = AMLAgent(llm=llm)

    team = Team(
        agents=[onboarding, aml],
        mode=TeamMode.SEQUENTIAL,
        name="ComplianceChain",
    )

    resp = team.run(Task(
        description="Mehmet Demo (TC: 12345678901) müşterisini onboard et ve AML değerlendir."
    ))
    print(resp.output)
    print("Zincir:", resp.metadata.get("chain"))


if __name__ == "__main__":
    main()
