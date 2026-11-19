"""Merge records found through overlapping firm searches."""

from __future__ import annotations

from dataclasses import replace

from pipeline.models import PartnerEntryInfo


def deduplicate_records(records: list[PartnerEntryInfo]) -> list[PartnerEntryInfo]:
    merged: dict[tuple[str, str], PartnerEntryInfo] = {}
    for record in records:
        key = (record.firm_key, record.profile_url)
        existing = merged.get(key)
        if existing is None:
            merged[key] = record
            continue
        merged[key] = replace(
            existing,
            offices=list(dict.fromkeys([*existing.offices, *record.offices])),
            practices=list(dict.fromkeys([*existing.practices, *record.practices])),
        )
    return list(merged.values())
