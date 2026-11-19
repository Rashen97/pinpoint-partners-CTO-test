"""Atomic JSON-backed storage for visible pipeline stage outputs."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pipeline.models import ExtractionResult, PartnerEntryInfo, PartnerProfileInfo


DEFAULT_DATABASE_ROOT = Path(__file__).parents[2] / "mock_database"
SAFE_KEY = re.compile(r"^[a-z0-9_]+$")


class JsonDatabase:
    def __init__(self, root: Path = DEFAULT_DATABASE_ROOT) -> None:
        self.root = root

    def save_connector_extraction(self, result: ExtractionResult) -> Path:
        """Save connector output for diagnostics, regardless of scope status."""
        return self._write(
            collection="connector_extractions",
            firm_key=result.firm_key,
            payload={
                "stage": "connector_extraction",
                "saved_at": self._now(),
                "firm_key": result.firm_key,
                "data": asdict(result),
            },
        )

    def save_partner_entries(self, result: ExtractionResult) -> Path:
        """Save only a complete, scope-verified unified roster."""
        if not result.extraction_complete:
            raise ValueError("Cannot save incomplete partner entries")
        if not result.scope_verified:
            raise ValueError("Cannot save partner entries with unverified scope")
        if any(not record.partner_entry_id for record in result.records):
            raise ValueError("Cannot save partner entries without internal IDs")
        return self._write(
            collection="partner_entries",
            firm_key=result.firm_key,
            payload={
                "stage": "partner_entries",
                "saved_at": self._now(),
                "firm_key": result.firm_key,
                "covered_practices": result.covered_practices,
                "record_count": len(result.records),
                "records": [asdict(record) for record in result.records],
            },
        )

    def save_all_partner_entries(
        self, results: list[ExtractionResult]
    ) -> Path:
        """Atomically replace the combined dataset after every firm succeeds."""
        if not results:
            raise ValueError("Cannot save an empty combined partner dataset")
        for result in results:
            if not result.extraction_complete or not result.scope_verified:
                raise ValueError(
                    f"Cannot combine incomplete or unverified firm: {result.firm_key}"
                )
        records = [record for result in results for record in result.records]
        if any(not record.partner_entry_id for record in records):
            raise ValueError("Cannot combine partner entries without internal IDs")
        unique = {
            (record.firm_key, record.profile_url): record
            for record in records
        }
        ordered = sorted(
            unique.values(),
            key=lambda record: (record.firm_key, record.name.casefold()),
        )
        return self._write(
            collection="partner_entries",
            firm_key="all_partners",
            payload={
                "stage": "all_partner_entries",
                "saved_at": self._now(),
                "firms": [result.firm_key for result in results],
                "record_count": len(ordered),
                "records": [asdict(record) for record in ordered],
            },
        )

    def load_all_partner_entries(self) -> list[PartnerEntryInfo]:
        """Load the unified schema boundary consumed by profile enrichment."""
        path = self.root / "partner_entries" / "all_partners.json"
        if not path.exists():
            raise FileNotFoundError(f"Unified partner dataset does not exist: {path}")
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("stage") != "all_partner_entries":
            raise ValueError(f"Unexpected stage in {path}")
        rows = document.get("records")
        if not isinstance(rows, list):
            raise ValueError(f"Unified partner dataset has no record list: {path}")
        fields = PartnerEntryInfo.__dataclass_fields__
        entries = [
            PartnerEntryInfo(
                **{key: value for key, value in row.items() if key in fields}
            )
            for row in rows
            if isinstance(row, dict)
        ]
        if len(entries) != document.get("record_count"):
            raise ValueError(f"Unified partner dataset count mismatch: {path}")
        return entries

    def save_all_partner_profiles(
        self,
        profiles: list[PartnerProfileInfo],
        failures: list[Any],
    ) -> Path:
        """Save the profile-enrichment stage for the combined dataset."""
        return self._write(
            collection="partner_profiles",
            firm_key="all_profiles",
            payload={
                "stage": "all_partner_profiles",
                "saved_at": self._now(),
                "profile_count": len(profiles),
                "failure_count": len(failures),
                "profiles": [asdict(profile) for profile in profiles],
                "failures": [asdict(failure) for failure in failures],
            },
        )

    def _write(
        self,
        collection: str,
        firm_key: str,
        payload: dict[str, Any],
    ) -> Path:
        if not SAFE_KEY.fullmatch(firm_key):
            raise ValueError(f"Unsafe firm key: {firm_key!r}")
        destination_dir = self.root / collection
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"{firm_key}.json"
        temporary = destination_dir / f".{firm_key}.{uuid4().hex}.tmp"
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        return destination

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
