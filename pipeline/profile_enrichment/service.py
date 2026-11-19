"""Dataset-wide profile enrichment service used by the refresh orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.models import PartnerEntryInfo, PartnerProfileInfo
from pipeline.profile_enrichment.base import ProfileConnector


@dataclass(frozen=True)
class ProfileEnrichmentFailure:
    firm_key: str
    profile_url: str
    error: str


@dataclass
class ProfileEnrichmentResult:
    profiles: list[PartnerProfileInfo] = field(default_factory=list)
    failures: list[ProfileEnrichmentFailure] = field(default_factory=list)


def enrich_entries(
    entries: list[PartnerEntryInfo],
    connector: ProfileConnector,
    limit: int | None = None,
) -> ProfileEnrichmentResult:
    """Enrich one unified dataset, continuing after individual failures."""
    selected = entries if limit is None else entries[:limit]
    result = ProfileEnrichmentResult()
    for entry in selected:
        try:
            result.profiles.append(connector.enrich(entry))
        except Exception as exc:
            result.failures.append(
                ProfileEnrichmentFailure(
                    firm_key=entry.firm_key,
                    profile_url=entry.profile_url,
                    error=str(exc),
                )
            )
    return result
