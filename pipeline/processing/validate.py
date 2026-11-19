"""Safety checks performed before a roster may be persisted."""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.models import ExtractionResult, PartnerEntryInfo


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_extraction(
    extraction: ExtractionResult,
    records: list[PartnerEntryInfo],
) -> ValidationResult:
    errors: list[str] = []
    if not extraction.extraction_complete:
        errors.append("Extraction did not complete")
    if not extraction.scope_verified:
        errors.append("Corporate/M&A scope has not been verified")
    if not records:
        errors.append("Extraction returned no in-scope records")
    for index, record in enumerate(records):
        if not record.name or not record.role or not record.profile_url:
            errors.append(f"Record {index} is missing a required field")
    return ValidationResult(
        valid=not errors,
        errors=errors,
        warnings=list(extraction.warnings),
    )
