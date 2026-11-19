"""Wachtell Lipton Corporate Partner directory connector."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo


class WachtellLiptonConnector(Connector):
    def __init__(
        self,
        firm_key: str,
        config: dict[str, Any],
        session: requests.Session | None = None,
    ) -> None:
        super().__init__(firm_key, config)
        self.session = session or build_session()

    def extract(self) -> ExtractionResult:
        endpoint = self.config.get("results_url")
        if not endpoint:
            raise ConnectorError("Wachtell results_url is missing")
        try:
            response = self.session.get(
                endpoint,
                params=self.config.get("query_params", {}),
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ConnectorError(f"Wachtell request failed: {exc}") from exc
        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type:
            raise UnexpectedResponseError("Wachtell returned a non-HTML response")

        records = self._parse(response.text, endpoint)
        minimum = int(self.config.get("minimum_expected_records", 5))
        if len(records) < minimum:
            raise UnexpectedResponseError(
                f"Wachtell returned only {len(records)} Corporate Partner profiles; "
                f"minimum safety threshold is {minimum}"
            )
        return ExtractionResult(
            firm_key=self.firm_key,
            records=records,
            pages_fetched=1,
            extraction_complete=True,
            scope_verified=True,
            covered_practices=["Corporate"],
            warnings=[
                "Wachtell publishes Corporate but no general M&A directory option; "
                "Real Estate M&A is not treated as equivalent."
            ],
        )

    def _parse(self, html: str, source_url: str) -> list[PartnerEntryInfo]:
        soup = BeautifulSoup(html, "html.parser")
        self._verify_selected_filter(soup, "asf_pa", "corporate")
        results = soup.select_one(".attorneys-search--results")
        if results is None or results.select_one(".pagination, .page-numbers, [rel='next']"):
            raise UnexpectedResponseError("Wachtell returned missing or paginated results")

        names_by_url: dict[str, str] = {}
        for row in results.select("li.attorneys-search--results-item:not(.attorneys-search--results-item-header)"):
            position = row.select_one(".attorneys-search--results-item-position")
            if position is None or not position.get_text(strip=True):
                raise UnexpectedResponseError("Wachtell result row is missing its position")
            if position.get_text(" ", strip=True).casefold() != "partner":
                continue

            link = row.select_one("a[href]")
            name_node = row.select_one(".attorneys-search--results-item-name")
            if link is None or name_node is None:
                raise UnexpectedResponseError("Wachtell partner row is missing a name or profile link")
            name = " ".join(name_node.stripped_strings)
            profile = urlparse(urljoin(source_url, link["href"]))
            if (
                not name or profile.scheme != "https"
                or profile.netloc != urlparse(source_url).netloc
                or not profile.path.startswith("/attorney/")
                or profile.path == "/attorney/"
            ):
                raise UnexpectedResponseError("Wachtell partner row has an invalid name or profile link")
            profile_url = profile._replace(path=profile.path.rstrip("/") + "/", query="", fragment="").geturl()
            names_by_url[profile_url] = name

        if not names_by_url:
            raise UnexpectedResponseError("Wachtell response contained no attorney profile links")
        return [
            PartnerEntryInfo(
                firm_key=self.firm_key,
                firm_name=self.config.get("name", ""),
                name=name,
                role="Partner",
                offices=[],
                practices=["Corporate"],
                profile_url=url,
                source_url=source_url,
            )
            for url, name in names_by_url.items()
        ]

    @staticmethod
    def _verify_selected_filter(soup: BeautifulSoup, name: str, value: str) -> None:
        selector = f'select[name="{name}"] option[value="{value}"][selected]'
        if soup.select_one(selector) is None:
            raise UnexpectedResponseError(
                f"Wachtell response did not confirm selected filter {name}={value}"
            )
