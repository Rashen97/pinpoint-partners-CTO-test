"""Paul, Weiss professional-directory connector."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo


class PaulWeissConnector(Connector):
    """Extract Partner rosters for the configured Corporate and M&A searches."""

    EXCLUDED_ROLE_TERMS = ("associate", "counsel", "retired")

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
        practices = self.config.get("practice_values")
        if not endpoint or not isinstance(practices, list) or not practices:
            raise ConnectorError("Paul Weiss endpoint or practice_values are missing")

        records_by_url: dict[str, PartnerEntryInfo] = {}
        pages_fetched = 0
        warnings: list[str] = []

        for practice in practices:
            practice_records, practice_pages = self._extract_practice(endpoint, practice)
            pages_fetched += practice_pages
            for record in practice_records:
                existing = records_by_url.get(record.profile_url)
                if existing is None:
                    records_by_url[record.profile_url] = record
                    continue
                existing.practices.extend(
                    label for label in record.practices if label not in existing.practices
                )
                existing.offices.extend(
                    office for office in record.offices if office not in existing.offices
                )

        return ExtractionResult(
            firm_key=self.firm_key,
            records=list(records_by_url.values()),
            pages_fetched=pages_fetched,
            extraction_complete=True,
            scope_verified=True,
            covered_practices=list(practices),
            warnings=warnings,
        )

    def _extract_practice(
        self, endpoint: str, practice: str
    ) -> tuple[list[PartnerEntryInfo], int]:
        first_html = self._fetch_page(endpoint, practice, 1)
        total = self._parse_total(first_html, practice)
        page_size = int(self.config["query_params"].get("pageSize", 12))
        final_page = max(1, math.ceil(total / page_size))
        pager_final = self._parse_final_page(first_html)
        if pager_final != final_page:
            raise UnexpectedResponseError(
                f"Paul Weiss {practice} pager ends at {pager_final}, "
                f"but total {total} with page size {page_size} implies {final_page}"
            )

        records: list[PartnerEntryInfo] = []
        seen_page_urls: set[frozenset[str]] = set()
        role_counts: Counter[str] = Counter()
        for page_number in range(1, final_page + 1):
            html = first_html if page_number == 1 else self._fetch_page(
                endpoint, practice, page_number
            )
            page_records = self._parse_records(html, endpoint, practice)
            page_soup = BeautifulSoup(html, "html.parser")
            role_counts.update(
                self._text(node.get_text(" ", strip=True))
                for node in page_soup.select(".outBio p.position")
            )
            page_urls = frozenset(record.profile_url for record in page_records)
            if not page_urls:
                raise UnexpectedResponseError(
                    f"Paul Weiss {practice} page {page_number} returned no Partner records"
                )
            if page_urls in seen_page_urls:
                raise UnexpectedResponseError(
                    f"Paul Weiss {practice} page {page_number} repeated an earlier page"
                )
            seen_page_urls.add(page_urls)
            records.extend(page_records)

        url_counts = Counter(record.profile_url for record in records)
        unique_records = {record.profile_url: record for record in records}
        if len(unique_records) != total:
            duplicates = sorted(url for url, count in url_counts.items() if count > 1)
            duplicate_detail = f"; repeated URLs: {', '.join(duplicates)}" if duplicates else ""
            raise UnexpectedResponseError(
                f"Paul Weiss {practice} reported {total} results but "
                f"{len(records)} Partner cards and {len(unique_records)} unique profiles "
                f"were parsed; card roles: {dict(role_counts)}{duplicate_detail}"
            )
        return list(unique_records.values()), final_page

    def _fetch_page(self, endpoint: str, practice: str, page_number: int) -> str:
        params = dict(self.config.get("query_params", {}))
        params[self.config.get("practice_param", "practices")] = practice
        params[self.config.get("page_param", "pagingNumber")] = page_number
        try:
            response = self.session.get(
                endpoint,
                params=params,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ConnectorError(
                f"Paul Weiss {practice} page {page_number} request failed: {exc}"
            ) from exc

        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type:
            raise UnexpectedResponseError(
                f"Paul Weiss {practice} page {page_number} returned "
                f"{content_type or 'an unknown content type'}, not HTML"
            )
        return response.text

    def _parse_records(
        self, html: str, source_url: str, practice: str
    ) -> list[PartnerEntryInfo]:
        soup = BeautifulSoup(html, "html.parser")
        records: list[PartnerEntryInfo] = []
        for card in soup.select(".outBio"):
            title_link = card.select_one(".bioTitle a[href]")
            role_node = card.select_one("p.position")
            if not isinstance(title_link, Tag) or not isinstance(role_node, Tag):
                continue
            role = self._text(role_node.get_text(" ", strip=True))
            if not role:
                raise UnexpectedResponseError("Paul Weiss result card is missing a role")
            if any(term in role.casefold() for term in self.EXCLUDED_ROLE_TERMS):
                raise UnexpectedResponseError(
                    f"Paul Weiss Partner-filtered results unexpectedly contained role '{role}'"
                )
            name = self._text(title_link.get_text(" ", strip=True))
            href = self._text(title_link.get("href"))
            if not name or not href:
                raise UnexpectedResponseError("Paul Weiss Partner card is missing name or URL")
            offices = [
                self._text(node.get_text(" ", strip=True))
                for node in card.select(".bioContent ul li")
                if self._text(node.get_text(" ", strip=True))
            ]
            records.append(
                PartnerEntryInfo(
                    firm_key=self.firm_key,
                    name=name,
                    role=role,
                    offices=list(dict.fromkeys(offices)),
                    practices=[practice],
                    profile_url=urljoin(self.config["directory_url"], href),
                    source_url=source_url,
                    firm_name=self.config.get("name", ""),
                )
            )
        return records

    @staticmethod
    def _parse_total(html: str, practice: str) -> int:
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.select_one(".testiTitle p")
        text = heading.get_text(" ", strip=True) if heading else ""
        match = re.search(r"Viewing\s+\d+\s+of\s+(\d+)", text, re.IGNORECASE)
        if not match:
            raise UnexpectedResponseError(
                f"Paul Weiss {practice} response did not contain a result total"
            )
        total = int(match.group(1))
        if total <= 0:
            raise UnexpectedResponseError(f"Paul Weiss {practice} returned an empty roster")
        return total

    @staticmethod
    def _parse_final_page(html: str) -> int:
        soup = BeautifulSoup(html, "html.parser")
        pages = []
        for node in soup.select("[data-page]"):
            value = node.get("data-page")
            if str(value).isdigit():
                pages.append(int(str(value)))
        return max(pages, default=1)

    @staticmethod
    def _text(value: Any) -> str:
        return " ".join(str(value or "").split())
