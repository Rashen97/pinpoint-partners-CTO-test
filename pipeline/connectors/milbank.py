"""Milbank public professional search with paginated attorney cards."""

from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo
from pipeline.processing.deduplicate import deduplicate_records


class MilbankConnector(Connector):
    def __init__(self, firm_key, config, session=None):
        super().__init__(firm_key, config)
        self.session = session or build_session()

    def extract(self) -> ExtractionResult:
        records = []
        pages = 0
        filters = self.config["practice_filters"]
        for practice in filters:
            batch, page_count = self._extract_practice(practice)
            records.extend(batch)
            pages += page_count
        return ExtractionResult(
            firm_key=self.firm_key,
            records=deduplicate_records(records),
            pages_fetched=pages,
            extraction_complete=True,
            scope_verified=self.config.get("scope_verified", False),
            covered_practices=[practice["label"] for practice in filters],
            warnings=self.config.get("scope_warnings", []),
        )

    def _extract_practice(self, practice) -> tuple[list[PartnerEntryInfo], int]:
        page_size = self.config["page_size"]
        total = None
        offset = 0
        pages = 0
        seen = set()
        partners = []
        while total is None or offset < total:
            try:
                response = self.session.get(
                    self.config["results_url"],
                    params={
                        "v": "attorney", "html": "", "f": offset, "s": page_size,
                        practice.get("param", "p"): practice["id"],
                    },
                    timeout=DEFAULT_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                payload = response.json()
                reported_total = payload["totals"]["ALL"]
                if (
                    type(reported_total) is not int or reported_total < 0
                    or (total is not None and reported_total != total)
                    or payload["offset"] != offset or payload["size"] != page_size
                ):
                    raise ValueError("result total or pagination changed")
                total = reported_total
                soup = BeautifulSoup(payload["rendered_view"], "html.parser")
                cards = soup.select(".card--attorney")
                if len(cards) != min(page_size, total - offset):
                    raise ValueError("card count does not match the reported total")
                for card in cards:
                    record = self._parse_card(card, practice["label"], response.url)
                    if record.profile_url in seen:
                        raise ValueError("duplicate profile URL across results")
                    seen.add(record.profile_url)
                    if record.role == "Partner":
                        partners.append(record)
            except requests.RequestException as exc:
                raise ConnectorError(f"Milbank {practice['label']} request failed: {exc}") from exc
            except (KeyError, TypeError, ValueError) as exc:
                raise UnexpectedResponseError(f"Invalid Milbank {practice['label']} results: {exc}") from exc
            offset += page_size
            pages += 1
        return partners, pages

    def _parse_card(self, card, practice, source_url) -> PartnerEntryInfo:
        link = card.select_one(".card__first-line a[href]")
        role = card.select_one(".card__second-line")
        if link is None or role is None or not link.get_text(" ", strip=True) or not role.get_text(strip=True):
            raise ValueError("attorney card is missing a name, link, or role")
        profile_url = urljoin(self.config["directory_url"], link["href"])
        profile = urlsplit(profile_url)
        if (
            profile.hostname != urlsplit(self.config["directory_url"]).hostname
            or not profile.path.startswith("/en/professionals/")
            or not profile.path.endswith(".html")
        ):
            raise ValueError("attorney link does not point to a Milbank profile")
        return PartnerEntryInfo(
            firm_key=self.firm_key,
            firm_name=self.config["name"],
            name=link.get_text(" ", strip=True),
            role=role.get_text(" ", strip=True),
            offices=[office.get_text(" ", strip=True) for office in card.select(".card__office-name a")],
            practices=[practice],
            profile_url=profile_url,
            source_url=source_url,
        )
