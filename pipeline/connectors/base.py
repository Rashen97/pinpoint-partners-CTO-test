"""Interface shared by all firm connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pipeline.models import ExtractionResult


class Connector(ABC):
    def __init__(self, firm_key: str, config: dict[str, Any]) -> None:
        self.firm_key = firm_key
        self.config = config

    @abstractmethod
    def extract(self) -> ExtractionResult:
        """Extract records without writing them to the database."""
