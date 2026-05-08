"""MASAK client interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from auraos.integrations.masak.models import (
        PEPMatch,
        SanctionMatch,
        SARCase,
        SARFilingResult,
        SARStatus,
    )


class MASAKClient(ABC):
    """Abstract interface for MASAK (Mali Suçları Araştırma Kurulu) integration.

    This interface defines the contract for:
    - Sanctions screening (UN, OFAC, EU, MASAK lists)
    - PEP (Politically Exposed Person) screening
    - SAR (Suspicious Activity Report) filing

    Implementations:
    - MASAKStubClient: For testing/development
    - MASAKRealClient: For production (connects to real MASAK systems)
    """

    @abstractmethod
    async def screen_sanctions(
        self,
        name: str,
        birth_date: date | None = None,
        id_number: str | None = None,
        country: str | None = None,
    ) -> list["SanctionMatch"]:
        """Screen against sanctions lists.

        Args:
            name: Name to screen
            birth_date: Date of birth for better matching
            id_number: ID number (TC, passport, etc.)
            country: Country code for filtering

        Returns:
            List of potential matches with scores
        """
        ...

    @abstractmethod
    async def screen_pep(
        self,
        name: str,
        country: str = "TR",
    ) -> list["PEPMatch"]:
        """Screen for Politically Exposed Persons.

        Args:
            name: Name to screen
            country: Country code to focus search

        Returns:
            List of potential PEP matches
        """
        ...

    @abstractmethod
    async def file_sar(
        self,
        case: "SARCase",
    ) -> "SARFilingResult":
        """File a Suspicious Activity Report.

        Args:
            case: The SAR case to file

        Returns:
            Filing result with reference number
        """
        ...

    @abstractmethod
    async def get_sar_status(
        self,
        case_id: str,
    ) -> "SARStatus":
        """Get the status of a filed SAR.

        Args:
            case_id: The SAR case ID

        Returns:
            Current status of the SAR
        """
        ...

    @abstractmethod
    async def get_sar(
        self,
        case_id: str,
    ) -> "SARCase | None":
        """Get a SAR case by ID.

        Args:
            case_id: The SAR case ID

        Returns:
            The SAR case or None if not found
        """
        ...
