"""Simpson Thacher's public WordPress staff listing."""

import math
import re
from time import sleep
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, Tag

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo
from pipeline.processing.deduplicate import deduplicate_records


class SimpsonThacherConnector(Connector):
    def __init__(self, firm_key, config, session=None):
        super().__init__(firm_key, config)
        self.session = session or build_session()

    def extract(self) -> ExtractionResult:
        records = []
        pages_fetched = 0
        filters = self.config["practice_page_filters"]
        for practice in filters:
            if pages_fetched:
                self._pace_requests()
            batch, pages = self._extract_practice(practice)
            records.extend(batch)
            pages_fetched += pages
        return ExtractionResult(
            firm_key=self.firm_key,
            records=deduplicate_records(records),
            pages_fetched=pages_fetched,
            extraction_complete=True,
            scope_verified=True,
            covered_practices=[practice["label"] for practice in filters],
        )

    def _extract_practice(self, practice) -> tuple[list[PartnerEntryInfo], int]:
        first = self._fetch(practice, 1)
        total = first.get("total_posts")
        page_size = first.get("current_posts")
        if (
            type(total) is not int or type(page_size) is not int
            or not 0 < page_size <= total
        ):
            raise UnexpectedResponseError("Simpson Thacher reported an invalid result total")

        page_count = math.ceil(total / page_size)
        records = []
        seen = set()
        for page in range(1, page_count + 1):
            if page == 1:
                payload = first
            else:
                self._pace_requests()
                payload = self._fetch(practice, page)
            offset = (page - 1) * page_size
            end = min(offset + page_size, total)
            html = payload.get("html")
            if (
                not isinstance(html, str)
                or payload.get("total_posts") != total
                or payload.get("start_post") != offset + 1
                or payload.get("end_post") != end
                or payload.get("current_posts") != end - offset
            ):
                raise UnexpectedResponseError(f"Simpson Thacher {practice['label']} page {page} has inconsistent counts")

            soup = BeautifulSoup(html, "html.parser")
            rows = soup.select('a[href*="/our-team/partners/"]:has(.wp-avatar-name)')
            if len(rows) != end - offset:
                raise UnexpectedResponseError(f"Simpson Thacher {practice['label']} page {page} has an unexpected card count")
            for row in rows:
                record = self._parse_row(row, practice)
                if record.profile_url in seen:
                    raise UnexpectedResponseError(f"Simpson Thacher {practice['label']} returned a duplicate profile")
                seen.add(record.profile_url)
                records.append(record)
        return records, page_count

    def _pace_requests(self) -> None:
        delay = self.config.get("request_interval_seconds", 0)
        if delay:
            sleep(delay)

    def _fetch(self, practice, page: int) -> dict:
        try:
            response = self.session.get(
                self.config["results_url"],
                params={
                    "position": self.config["partner_position_id"],
                    "practice": practice["id"],
                    "paged": page,
                },
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ConnectorError(f"Simpson Thacher {practice['label']} page {page} request failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise UnexpectedResponseError("Simpson Thacher returned invalid listing JSON")
        return payload

    def _parse_row(self, row: Tag, practice) -> PartnerEntryInfo:
        source = self.config["directory_url"]
        name_node = row.select_one(".wp-avatar-name")
        role_node = row.select_one(".wp-avatar-position")
        name = name_node.get_text(" ", strip=True) if name_node else ""
        role = role_node.get_text(" ", strip=True) if role_node else ""
        profile = urlsplit(urljoin(source, row["href"]))
        practice_nodes = row.select('[data-filter-name="practice"]')
        if (
            not name or not re.search(r"\bPartner\b", role)
            or profile.scheme != "https" or profile.netloc != urlsplit(source).netloc
            or not re.fullmatch(r"/our-team/partners/[^/]+/?", profile.path)
            or str(practice["id"]) not in {node.get("data-filter-id") for node in practice_nodes}
        ):
            raise UnexpectedResponseError("Simpson Thacher returned a card outside the requested partner practice")
        return PartnerEntryInfo(
            firm_key=self.firm_key,
            firm_name=self.config["name"],
            name=name,
            role=role,
            offices=[node.get_text(" ", strip=True) for node in row.select('[data-filter-name="office"]')],
            practices=[node.get_text(" ", strip=True) for node in practice_nodes],
            profile_url=profile._replace(query="", fragment="").geturl(),
            source_url=source,
        )
