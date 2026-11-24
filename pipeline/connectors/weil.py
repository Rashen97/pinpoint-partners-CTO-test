"""Read Weil's public People search for documented Corporate practices."""

from math import ceil
from time import sleep
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo
from pipeline.processing.deduplicate import deduplicate_records


PRACTICE_PARAM = "param_practices_sm|primary_practice_s|additional_primary_practices_sm"


class WeilConnector(Connector):
    def __init__(self, firm_key, config, session=None):
        super().__init__(firm_key, config)
        self.session = session or build_session()

    def extract(self) -> ExtractionResult:
        records = []
        covered = []
        pages_fetched = 0
        for practice, practice_id in self.config["practice_filters"].items():
            entries, pages = self._extract_practice(practice, practice_id)
            records.extend(entries)
            covered.append(practice)
            pages_fetched += pages

        excluded = {record.profile_url for record in records if record.role.casefold() != "partner"}
        warnings = ["Coverage of Corporate practices without an exact directory filter is unverified."]
        if excluded:
            warnings.append(f"Excluded {len(excluded)} profiles with displayed titles other than Partner.")
        return ExtractionResult(
            firm_key=self.firm_key,
            records=deduplicate_records([record for record in records if record.profile_url not in excluded]),
            pages_fetched=pages_fetched,
            extraction_complete=True,
            scope_verified=False,
            covered_practices=covered,
            missing_practices=["Full Corporate scope"],
            warnings=warnings,
        )

    def _extract_practice(self, practice, practice_id):
        records = []
        page = 1
        pages = 1
        total = None
        page_size = self.config["page_size"]
        while page <= pages:
            payload, source = self._fetch(page, practice_id)
            if page == 1:
                total = payload.get("TotalCount")
                if type(total) is not int or total <= 0:
                    raise UnexpectedResponseError(f"Weil {practice} returned an invalid result total")
                pages = ceil(total / page_size)
            if any(
                type(payload.get(key)) is not int or payload[key] != expected
                for key, expected in (
                    ("TotalCount", total), ("TotalPages", pages),
                    ("PageNumber", page), ("PageSize", page_size),
                )
            ):
                raise UnexpectedResponseError(f"Weil {practice} pagination disagreed on page {page}")
            groups = payload.get("SearchGroups")
            if not isinstance(groups, list) or not groups:
                raise UnexpectedResponseError(f"Weil {practice} page {page} has no result groups")
            page_records = []
            for group in groups:
                cards = group.get("SearchResultItemsAsHtml") if isinstance(group, dict) else None
                if not isinstance(cards, list) or any(not isinstance(card, str) for card in cards):
                    raise UnexpectedResponseError(f"Weil {practice} page {page} has malformed cards")
                page_records.extend(self._parse_card(card, source, practice) for card in cards)
            if not page_records:
                raise UnexpectedResponseError(f"Weil {practice} page {page} has no profile cards")
            records.extend(page_records)
            page += 1
        unique = len({record.profile_url for record in records})
        if unique != total:
            raise UnexpectedResponseError(f"Weil {practice} reported {total} results but returned {unique} profiles")
        return records, pages

    def _fetch(self, page, practice_id):
        sleep(self.config["request_interval_seconds"])
        try:
            response = self.session.get(
                self.config["results_url"],
                params={
                    "pagenum": page,
                    "pagesize": self.config["page_size"],
                    "itemId": self.config["item_id"],
                    "param_role_s": self.config["partner_role_id"],
                    PRACTICE_PARAM: practice_id,
                },
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ConnectorError(f"Weil directory request failed on page {page}: {exc}") from exc
        if not isinstance(payload, dict):
            raise UnexpectedResponseError(f"Weil returned an invalid response on page {page}")
        return payload, response.url

    def _parse_card(self, card, source, practice):
        soup = BeautifulSoup(card, "html.parser")
        link = soup.select_one("h3 a[href]")
        title = soup.select_one(".ppl-item-status b")
        name = link.get_text(" ", strip=True) if link else ""
        role = title.get_text(" ", strip=True) if title else ""
        directory = self.config["directory_url"]
        profile = urlsplit(urljoin(directory, link["href"])) if link else urlsplit("")
        path = profile.path.rstrip("/")
        if (
            not name or not role
            or profile.scheme != "https" or profile.netloc != urlsplit(directory).netloc
            or path.rsplit("/", 1)[0] != "/people" or not path.rsplit("/", 1)[-1]
        ):
            raise UnexpectedResponseError(f"Weil {practice} card has an invalid name, title or profile link")
        return PartnerEntryInfo(
            firm_key=self.firm_key,
            firm_name=self.config["name"],
            name=name,
            role=role,
            offices=[node.get_text(" ", strip=True) for node in soup.select(".ppl-item-status a")],
            practices=list(dict.fromkeys([
                practice, *[node.get_text(" ", strip=True) for node in soup.select(".ppl-item-categories a")],
            ])),
            profile_url=profile._replace(path=path, query="", fragment="").geturl(),
            source_url=source,
        )
