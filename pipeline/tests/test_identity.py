from __future__ import annotations

import unittest

from pipeline.models import PartnerEntryInfo
from pipeline.processing.identity import (
    canonicalize_profile_url,
    create_partner_entry_id,
)
from pipeline.processing.normalize import normalize_record


class PartnerIdentityTests(unittest.TestCase):
    def test_equivalent_urls_produce_the_same_id(self) -> None:
        first = create_partner_entry_id(
            "example", "HTTPS://EXAMPLE.COM:443/lawyers/alex/"
        )
        second = create_partner_entry_id(
            "example", "https://example.com/lawyers/alex#overview"
        )
        self.assertEqual(first, second)

    def test_same_url_at_different_firms_produces_different_ids(self) -> None:
        url = "https://example.com/lawyers/alex"
        self.assertNotEqual(
            create_partner_entry_id("first_firm", url),
            create_partner_entry_id("second_firm", url),
        )

    def test_normalization_assigns_id_from_canonical_url(self) -> None:
        record = PartnerEntryInfo(
            firm_key="example",
            firm_name="Example Firm",
            name="Alex Example",
            role="Partner",
            offices=[],
            practices=["Corporate"],
            profile_url="HTTPS://EXAMPLE.COM:443/lawyers/alex/#bio",
            source_url="https://example.com/directory",
        )

        normalized = normalize_record(record)

        self.assertEqual(
            normalized.profile_url,
            canonicalize_profile_url(record.profile_url),
        )
        self.assertEqual(
            normalized.partner_entry_id,
            create_partner_entry_id("example", normalized.profile_url),
        )


if __name__ == "__main__":
    unittest.main()
