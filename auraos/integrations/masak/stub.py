"""MASAK stub client for testing."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from auraos.integrations.masak.interface import MASAKClient
from auraos.integrations.masak.models import (
    PEPMatch,
    SanctionMatch,
    SARCase,
    SARFilingResult,
    SARStatus,
)


class MASAKStubClient(MASAKClient):
    """Stub implementation for testing and development.

    Pre-loaded with realistic test data for Turkish banking scenarios.
    """

    def __init__(
        self,
        sanctions_data: list[SanctionMatch] | None = None,
        pep_data: list[PEPMatch] | None = None,
        default_match_threshold: float = 0.75,
    ) -> None:
        self._sanctions = sanctions_data or self._default_sanctions()
        self._peps = pep_data or self._default_peps()
        self._sars: dict[str, SARCase] = {}
        self._filing_counter = 1000
        self.match_threshold = default_match_threshold

    def _default_sanctions(self) -> list[SanctionMatch]:
        """Default sanctions test data."""
        return [
            SanctionMatch(
                list_name="UN",
                matched_name="Test Sanctioned Person",
                match_score=1.0,
                list_id="UN-TAL-001",
                sanctions_type="terrorism",
                effective_date=date(2020, 1, 15),
                country="TR",
            ),
            SanctionMatch(
                list_name="OFAC",
                matched_name="Test OFAC Entity",
                match_score=0.95,
                list_id="OFAC-SDN-12345",
                sanctions_type="financial",
                effective_date=date(2019, 6, 1),
                country="US",
            ),
            SanctionMatch(
                list_name="MASAK",
                matched_name="Test MASAK Listed",
                match_score=0.98,
                list_id="MASAK-2023-001",
                sanctions_type="money_laundering",
                effective_date=date(2023, 3, 20),
                country="TR",
            ),
        ]

    def _default_peps(self) -> list[PEPMatch]:
        """Default PEP test data."""
        return [
            PEPMatch(
                name="Test Politician",
                position="Milletvekili",
                country="TR",
                match_score=0.92,
                level="national",
                status="active",
                start_date=date(2018, 6, 24),
            ),
            PEPMatch(
                name="Test Mayor",
                position="Belediye Başkanı",
                country="TR",
                match_score=0.88,
                level="regional",
                status="active",
                start_date=date(2019, 4, 1),
            ),
        ]

    def _fuzzy_match(self, name1: str, name2: str) -> float:
        """Simple fuzzy matching for testing."""
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()

        if n1 == n2:
            return 1.0
        if n1 in n2 or n2 in n1:
            return 0.85

        words1 = set(n1.split())
        words2 = set(n2.split())
        common = len(words1 & words2)
        total = len(words1 | words2)
        return common / total if total > 0 else 0.0

    async def screen_sanctions(
        self,
        name: str,
        birth_date: date | None = None,
        id_number: str | None = None,
        country: str | None = None,
    ) -> list[SanctionMatch]:
        matches = []
        for sanction in self._sanctions:
            score = self._fuzzy_match(name, sanction.matched_name)
            if score >= self.match_threshold:
                match = SanctionMatch(
                    list_name=sanction.list_name,
                    matched_name=sanction.matched_name,
                    match_score=score,
                    list_id=sanction.list_id,
                    sanctions_type=sanction.sanctions_type,
                    effective_date=sanction.effective_date,
                    country=sanction.country,
                )
                matches.append(match)
        return sorted(matches, key=lambda m: -m.match_score)

    async def screen_pep(
        self,
        name: str,
        country: str = "TR",
    ) -> list[PEPMatch]:
        matches = []
        for pep in self._peps:
            if country and pep.country != country:
                continue
            score = self._fuzzy_match(name, pep.name)
            if score >= self.match_threshold:
                match = PEPMatch(
                    name=pep.name,
                    position=pep.position,
                    country=pep.country,
                    match_score=score,
                    level=pep.level,
                    status=pep.status,
                    start_date=pep.start_date,
                    end_date=pep.end_date,
                )
                matches.append(match)
        return sorted(matches, key=lambda m: -m.match_score)

    async def file_sar(
        self,
        case: SARCase,
    ) -> SARFilingResult:
        self._filing_counter += 1
        filing_ref = f"MASAK-SAR-{datetime.now().year}-{self._filing_counter:06d}"

        case.status = SARStatus.FILED
        case.filed_at = datetime.now()
        case.filing_reference = filing_ref
        self._sars[case.id] = case

        return SARFilingResult(
            success=True,
            case_id=case.id,
            filing_reference=filing_ref,
            filed_at=case.filed_at,
        )

    async def get_sar_status(
        self,
        case_id: str,
    ) -> SARStatus:
        case = self._sars.get(case_id)
        if case:
            return case.status
        return SARStatus.DRAFT

    async def get_sar(
        self,
        case_id: str,
    ) -> SARCase | None:
        return self._sars.get(case_id)

    def add_sar(self, case: SARCase) -> None:
        """Add a SAR case (for testing setup)."""
        self._sars[case.id] = case
