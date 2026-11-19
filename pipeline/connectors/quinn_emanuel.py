"""Read Quinn Emanuel's public M&A Litigation practice team."""

from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo


class QuinnEmanuelConnector(Connector):
    def __init__(self, firm_key, config, session=None):
        super().__init__(firm_key, config)
        self.session = session or build_session()

    def extract(self) -> ExtractionResult:
        source = self.config["practice_reference_url"]
        size = self.config["practice_page_size"]
        practice = self.config["practice_label"]
        try:
            response = self.session.post(
                self.config["practice_results_url"],
                params={"page": 1, "size": size, "id": self.config["practice_id"]},
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ConnectorError(f"Quinn Emanuel practice team request failed: {exc}") from exc

        soup = BeautifulSoup(response.text, "html.parser")
        team = soup.select_one("#partners")
        cards = team.select(".attorney-card") if team is not None else []
        returned_size = soup.select_one("input#Size")
        if (
            not 0 < len(cards) < size
            or returned_size is None
            or returned_size.get("value") != str(size)
            or team.select_one(".pagination, [onclick*='LoadAttorneys']")
        ):
            raise UnexpectedResponseError("Quinn Emanuel practice team may be empty or truncated")

        records = []
        seen = set()
        for card in cards:
            link = card.select_one(".atn-des h3 a[href]")
            designation = card.select_one(".atn-des .designation")
            if link is None or designation is None:
                raise UnexpectedResponseError("Quinn Emanuel card is missing a profile link or role")
            name = link.get_text(" ", strip=True)
            role = designation.get_text(" ", strip=True)
            profile_url = urljoin(source, link["href"]).rstrip("/") + "/"
            profile = urlsplit(profile_url)
            if (
                not name or not role or profile.hostname != urlsplit(source).hostname
                or not profile.path.startswith("/attorneys/")
                or profile.path == "/attorneys/" or profile_url in seen
            ):
                raise UnexpectedResponseError("Quinn Emanuel card has an invalid or duplicate profile")
            seen.add(profile_url)
            if role.split(",", 1)[0].strip() == "Partner":
                records.append(PartnerEntryInfo(
                    firm_key=self.firm_key,
                    firm_name=self.config["name"],
                    name=name,
                    role=role,
                    offices=[office.get_text(" ", strip=True) for office in card.select(".location a")],
                    practices=[practice],
                    profile_url=profile_url,
                    source_url=source,
                ))
        if not records:
            raise UnexpectedResponseError("Quinn Emanuel practice team returned no partners")
        return ExtractionResult(
            firm_key=self.firm_key,
            records=records,
            pages_fetched=1,
            expected_total=len(records),
            extraction_complete=True,
            scope_verified=True,
            covered_practices=[practice],
        )
