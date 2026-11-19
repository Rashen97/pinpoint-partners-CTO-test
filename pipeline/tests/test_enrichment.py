from __future__ import annotations

import unittest

from pipeline.models import PartnerEntryInfo, PartnerProfileInfo
from pipeline.profile_enrichment.base import ProfileConnector
from pipeline.profile_enrichment.service import enrich_entries


def entry(name: str) -> PartnerEntryInfo:
    return PartnerEntryInfo(
        firm_key="example",
        firm_name="Example Firm",
        name=name,
        role="Partner",
        offices=["London"],
        practices=["Corporate"],
        profile_url=f"https://example.com/{name.casefold()}",
        source_url="https://example.com/directory",
        partner_entry_id=f"entry-{name.casefold()}",
    )


class FakeConnector(ProfileConnector):
    def enrich(self, item: PartnerEntryInfo) -> PartnerProfileInfo:
        if item.name == "Failure":
            raise RuntimeError("profile unavailable")
        return PartnerProfileInfo(
            firm_key=item.firm_key,
            name=item.name,
            profile_url=item.profile_url,
            role=item.role,
            offices=item.offices,
            practices=item.practices,
            biography="Biography",
            phone_numbers=[],
            email=None,
            education=[],
            admissions=[],
            languages=[],
            source_checked_at="2026-11-18T00:00:00+00:00",
            content_hash="a" * 64,
            partner_entry_id=item.partner_entry_id,
        )


class EnrichmentTests(unittest.TestCase):
    def test_continues_after_an_individual_profile_failure(self) -> None:
        result = enrich_entries(
            [entry("First"), entry("Failure"), entry("Third")],
            FakeConnector(),
        )

        self.assertEqual([profile.name for profile in result.profiles], ["First", "Third"])
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.failures[0].error, "profile unavailable")

    def test_limit_is_applied_to_the_unified_dataset(self) -> None:
        result = enrich_entries(
            [entry("First"), entry("Second")],
            FakeConnector(),
            limit=1,
        )

        self.assertEqual([profile.name for profile in result.profiles], ["First"])


if __name__ == "__main__":
    unittest.main()
