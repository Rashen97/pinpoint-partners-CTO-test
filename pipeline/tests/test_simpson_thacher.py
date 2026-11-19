import unittest

from pipeline.connectors.errors import UnexpectedResponseError
from pipeline.connectors.simpson_thacher import SimpsonThacherConnector


CONFIG = {
    "name": "Simpson Thacher & Bartlett",
    "directory_url": "https://www.stblaw.com/our-team/",
    "results_url": "https://www.stblaw.com/wp-json/stb/v1/staff-listing",
    "partner_position_id": "7972",
    "practice_page_filters": [
        {"label": "Corporate", "id": "corporate-id"},
        {"label": "Mergers and Acquisitions", "id": "ma-id"},
    ],
}


class FakeResponse:
    def __init__(self, practice, page):
        self.practice = practice
        self.page = page

    def raise_for_status(self):
        return None

    def json(self):
        slug = "adam-s--aderton" if self.page == 1 else "another-partner"
        return {
            "total_posts": 2,
            "current_posts": 1,
            "start_post": self.page,
            "end_post": self.page,
            "html": f"""
                <a href="/our-team/partners/{slug}/">
                  <h3 class="wp-avatar-name">Example Person</h3>
                  <p class="wp-avatar-position">Chair, Partner</p>
                  <span data-filter-name="office">New York</span>
                  <span data-filter-name="practice" data-filter-id="{self.practice}">Practice {self.practice}</span>
                </a>
            """,
        }


class FakeSession:
    def __init__(self, repeat_page=False):
        self.repeat_page = repeat_page

    def get(self, url, params, timeout):
        return FakeResponse(params["practice"], 1 if self.repeat_page else params["paged"])


class SimpsonThacherTests(unittest.TestCase):
    def test_checks_pagination_and_merges_overlapping_practices(self):
        result = SimpsonThacherConnector("simpson_thacher", CONFIG, FakeSession()).extract()
        self.assertTrue(result.scope_verified)
        self.assertEqual(result.pages_fetched, 4)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.covered_practices, ["Corporate", "Mergers and Acquisitions"])
        first = result.records[0]
        self.assertTrue(first.profile_url.endswith("/adam-s--aderton/"))
        self.assertEqual(first.offices, ["New York"])
        self.assertEqual(first.practices, ["Practice corporate-id", "Practice ma-id"])
        self.assertEqual(first.role, "Chair, Partner")

    def test_rejects_repeated_page_counts(self):
        connector = SimpsonThacherConnector("simpson_thacher", CONFIG, FakeSession(repeat_page=True))
        with self.assertRaisesRegex(UnexpectedResponseError, "page 2 has inconsistent counts"):
            connector.extract()
