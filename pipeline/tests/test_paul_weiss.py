from __future__ import annotations

import unittest

from pipeline.connectors.errors import UnexpectedResponseError
from pipeline.connectors.paul_weiss import PaulWeissConnector


CONFIG = {
    "directory_url": "https://www.paulweiss.com/professionals",
    "results_url": "https://www.paulweiss.com/results",
    "query_params": {"pageSize": 2, "pagingNumber": 1, "position": "Partner"},
    "practice_param": "practices",
    "practice_values": ["Corporate", "Mergers and Acquisitions"],
    "page_param": "pagingNumber",
}


def page(total: int, people: list[tuple[str, str, str]], final_page: int = 1) -> str:
    cards = "".join(
        f"""
        <div class="outBio">
          <div class="bioTitle"><a href="{url}"><p>{name}</p></a></div>
          <div class="bioContent">
            <p class="position">{role}</p><ul><li>London</li></ul>
          </div>
        </div>
        """
        for name, role, url in people
    )
    pager = "".join(f'<a data-page="{number}">{number}</a>' for number in range(1, final_page + 1))
    return f'<div class="testiTitle"><p>Viewing {len(people)} of {total}</p></div>{cards}{pager}'


class FakeResponse:
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self, responses: dict[tuple[str, int], str]) -> None:
        self.responses = responses

    def get(self, url, params, timeout):
        key = (params["practices"], params["pagingNumber"])
        return FakeResponse(self.responses[key])


class PaulWeissConnectorTests(unittest.TestCase):
    def test_extracts_pages_and_merges_practice_overlap(self) -> None:
        responses = {
            ("Corporate", 1): page(
                2,
                [
                    ("Alex One", "Partner", "/professionals/partners-and-counsel/alex-one"),
                    ("Blair Two", "Partner", "/professionals/partners-and-counsel/blair-two"),
                ],
            ),
            ("Mergers and Acquisitions", 1): page(
                3,
                [
                    ("Blair Two", "Partner", "/professionals/partners-and-counsel/blair-two"),
                    ("Casey Three", "Partner", "/professionals/partners-and-counsel/casey-three"),
                ],
                final_page=2,
            ),
            ("Mergers and Acquisitions", 2): page(
                3,
                [("Devon Four", "Partner", "/professionals/partners-and-counsel/devon-four")],
                final_page=2,
            ),
        }
        connector = PaulWeissConnector("paul_weiss", CONFIG, FakeSession(responses))

        result = connector.extract()

        self.assertTrue(result.extraction_complete)
        self.assertTrue(result.scope_verified)
        self.assertEqual(result.pages_fetched, 3)
        self.assertEqual(len(result.records), 4)
        overlap = next(record for record in result.records if record.name == "Blair Two")
        self.assertEqual(
            overlap.practices,
            ["Corporate", "Mergers and Acquisitions"],
        )

    def test_rejects_count_mismatch(self) -> None:
        connector = PaulWeissConnector("paul_weiss", CONFIG, FakeSession({}))
        html = page(
            2,
            [("Alex One", "Partner", "/professionals/partners-and-counsel/alex-one")],
        )

        with self.assertRaisesRegex(UnexpectedResponseError, "reported 2 results"):
            self._extract_mismatch(connector, html)

    def test_preserves_leadership_title_from_partner_filtered_result(self) -> None:
        connector = PaulWeissConnector("paul_weiss", CONFIG, FakeSession({}))
        html = page(
            1,
            [("Alex Leader", "Deputy Chair", "/professionals/partners-and-counsel/alex-leader")],
        )

        records = connector._parse_records(
            html, CONFIG["results_url"], "Corporate"
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].role, "Deputy Chair")

    def test_rejects_counsel_in_partner_filtered_result(self) -> None:
        connector = PaulWeissConnector("paul_weiss", CONFIG, FakeSession({}))
        html = page(
            1,
            [("Casey Counsel", "Public Counsel", "/professionals/partners-and-counsel/casey")],
        )

        with self.assertRaisesRegex(UnexpectedResponseError, "Public Counsel"):
            connector._parse_records(html, CONFIG["results_url"], "Corporate")

    @staticmethod
    def _extract_mismatch(connector: PaulWeissConnector, html: str) -> None:
        connector.session = FakeSession({("Corporate", 1): html})
        connector._extract_practice(CONFIG["results_url"], "Corporate")


if __name__ == "__main__":
    unittest.main()
