"""Conservative cleanup that does not change source meaning."""

from __future__ import annotations

from dataclasses import replace

from pipeline.models import PartnerEntryInfo
from pipeline.processing.identity import (
    canonicalize_profile_url,
    create_partner_entry_id,
)


def normalize_record(record: PartnerEntryInfo) -> PartnerEntryInfo:
    profile_url = canonicalize_profile_url(record.profile_url)
    return replace(
        record,
        name=_clean(record.name),
        role=_clean(record.role),
        offices=_unique_clean(record.offices),
        practices=_unique_clean(record.practices),
        profile_url=profile_url,
        source_url=record.source_url.strip(),
        partner_entry_id=(
            record.partner_entry_id
            or create_partner_entry_id(record.firm_key, profile_url)
        ),
    )


def normalize_records(records: list[PartnerEntryInfo]) -> list[PartnerEntryInfo]:
    return [normalize_record(record) for record in records]


def _clean(value: str) -> str:
    return " ".join(value.split())


def _unique_clean(values: list[str]) -> list[str]:
    return list(dict.fromkeys(_clean(value) for value in values if _clean(value)))
