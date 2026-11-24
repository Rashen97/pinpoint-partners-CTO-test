"""Source-independent target models returned by every firm connector."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PartnerEntryInfo:
    """Canonical roster record while preserving each firm's native labels.

    This is deliberately a roster model, not a biography or CRM model. Fields
    such as employment history and AI summaries belong in separate enrichment
    tables with their own sources and freshness timestamps.
    """

    firm_key: str
    name: str
    role: str
    offices: list[str]
    practices: list[str]
    profile_url: str
    source_url: str
    firm_name: str = ""
    source_record_id: str | None = None
    partner_entry_id: str = ""


@dataclass(frozen=True)
class PartnerProfileInfo:
    """Source-backed information extracted from an individual profile page."""

    firm_key: str
    name: str
    profile_url: str
    role: str | None
    offices: list[str]
    practices: list[str]
    biography: str | None
    phone_numbers: list[str]
    email: str | None
    education: list[str]
    admissions: list[str]
    languages: list[str]
    source_checked_at: str
    content_hash: str
    partner_entry_id: str = ""


# Transitional aliases keep existing connectors compatible while the name change
# is rolled through the codebase.
TargetPartner = PartnerEntryInfo
ExtractedPartner = PartnerEntryInfo


@dataclass
class ExtractionResult:
    firm_key: str
    records: list[PartnerEntryInfo] = field(default_factory=list)
    pages_fetched: int = 0
    expected_total: int | None = None
    extraction_complete: bool = False
    scope_verified: bool = False
    covered_practices: list[str] = field(default_factory=list)
    missing_practices: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    directory_summaries: dict[str, str | None] = field(default_factory=dict)
