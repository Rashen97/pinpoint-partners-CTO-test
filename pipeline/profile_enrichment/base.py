"""Interface for enriching a unified partner entry."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pipeline.models import PartnerEntryInfo, PartnerProfileInfo


class ProfileConnector(ABC):
    @abstractmethod
    def enrich(self, entry: PartnerEntryInfo) -> PartnerProfileInfo:
        """Fetch and parse one profile URL."""
