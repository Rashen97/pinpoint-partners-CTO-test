"""Dataset-wide profile enrichment service used by the refresh orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from pipeline.connectors.errors import ProfileRateLimitError, UnexpectedResponseError
from pipeline.models import PartnerEntryInfo, PartnerProfileInfo
from pipeline.profile_enrichment.base import ProfileConnector
from pipeline.profile_enrichment.connector import with_content_hash


@dataclass(frozen=True)
class ProfileEnrichmentFailure:
    firm_key: str
    profile_url: str
    error: str


@dataclass
class ProfileEnrichmentResult:
    profiles: list[PartnerProfileInfo] = field(default_factory=list)
    failures: list[ProfileEnrichmentFailure] = field(default_factory=list)
    retry_times: dict[str, str] = field(default_factory=dict)


def retry_time(retry_after: str | None, now: datetime) -> str:
    if retry_after:
        try:
            if retry_after.isascii() and retry_after.isdecimal():
                return (now + timedelta(seconds=int(retry_after))).isoformat(timespec="microseconds")
            retry_at = parsedate_to_datetime(retry_after)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(now, retry_at.astimezone(timezone.utc)).isoformat(timespec="microseconds")
        except (ValueError, OverflowError):
            pass
    return (now + timedelta(minutes=30)).isoformat(timespec="microseconds")


def enrich_entries(
    entries: list[PartnerEntryInfo],
    connector: ProfileConnector,
    limit: int | None = None,
    directory_summaries: dict[tuple[str, str], str | None] | None = None,
) -> ProfileEnrichmentResult:
    """Enrich one unified dataset, continuing after individual failures."""
    selected = entries if limit is None else entries[:limit]
    result = ProfileEnrichmentResult()
    summaries = directory_summaries or {}
    for entry in selected:
        if entry.firm_key in result.retry_times:
            continue
        try:
            key = (entry.firm_key, entry.profile_url)
            profile = _directory_profile(entry, summaries[key]) if key in summaries else connector.enrich(entry)
            result.profiles.append(profile)
        except Exception as exc:
            if isinstance(exc, ProfileRateLimitError):
                result.retry_times[entry.firm_key] = retry_time(exc.retry_after, datetime.now(timezone.utc))
            result.failures.append(
                ProfileEnrichmentFailure(
                    firm_key=entry.firm_key,
                    profile_url=entry.profile_url,
                    error=str(exc),
                )
            )
    return result


def _directory_profile(entry: PartnerEntryInfo, summary: str | None) -> PartnerProfileInfo:
    if not summary:
        raise UnexpectedResponseError("Directory result did not include a profile summary")
    return with_content_hash(PartnerProfileInfo(
        firm_key=entry.firm_key, partner_entry_id=entry.partner_entry_id,
        name=entry.name, profile_url=entry.profile_url, role=entry.role,
        offices=entry.offices, practices=entry.practices, biography=" ".join(summary.split()),
        phone_numbers=[], email=None, education=[], admissions=[], languages=[],
        source_checked_at=datetime.now(timezone.utc).isoformat(), content_hash="",
    ))
