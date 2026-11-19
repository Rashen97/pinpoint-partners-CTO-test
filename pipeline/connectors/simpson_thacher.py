"""Simpson Thacher public team-directory connector."""

from __future__ import annotations

import math
from typing import Any
from urllib.parse import urljoin

import requests

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo


class SimpsonThacherConnector(Connector):
    def __init__(
        self,
        firm_key: str,
        config: dict[str, Any],
        session: requests.Session | None = None,
    ) -> None:
        super().__init__(firm_key, config)
        self.session = session or build_session()
        self.session.headers.update({"X-Requested-With": "XMLHttpRequest"})

    def extract(self) -> ExtractionResult:
        endpoint = self.config.get("results_url")
        filters = self.config.get("practice_page_filters", [])
        if not endpoint or not filters:
            raise ConnectorError("Simpson Thacher endpoint or practice page filters are missing")

        records_by_url: dict[str, PartnerEntryInfo] = {}
        pages_fetched = 0
        for practice in filters:
            records, pages = self._extract_practice(
                endpoint, str(practice["id"]), str(practice["label"])
            )
            pages_fetched += pages
            for record in records:
                existing = records_by_url.get(record.profile_url)
                if existing is None:
                    records_by_url[record.profile_url] = record
                else:
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
            covered_practices=[str(item["label"]) for item in filters],
        )

    def _extract_practice(
        self, endpoint: str, practice_id: str, practice_label: str
    ) -> tuple[list[PartnerEntryInfo], int]:
        page_size = int(self.config.get("page_size", 100))
        first = self._fetch(endpoint, practice_id, 1, page_size)
        total = first.get(self.config.get("total_key", "total"))
        if not isinstance(total, int) or total <= 0:
            raise UnexpectedResponseError(
                f"Simpson Thacher {practice_label} returned an invalid total"
            )
        page_count = math.ceil(total / page_size)
        records: list[PartnerEntryInfo] = []
        for page_number in range(1, page_count + 1):
            payload = first if page_number == 1 else self._fetch(
                endpoint, practice_id, page_number, page_size
            )
            rows = payload.get(self.config.get("records_key", "TeamModels"))
            if not isinstance(rows, list) or not rows:
                raise UnexpectedResponseError(
                    f"Simpson Thacher {practice_label} page {page_number} has no rows"
                )
            records.extend(
                self._parse_row(row, endpoint, practice_label)
                for row in rows
                if isinstance(row, dict)
            )

        unique = {record.profile_url: record for record in records}
        if len(records) != total or len(unique) != total:
            raise UnexpectedResponseError(
                f"Simpson Thacher {practice_label} reported {total} but parsed "
                f"{len(records)} rows and {len(unique)} unique profiles"
            )
        return list(unique.values()), page_count

    def _fetch(
        self, endpoint: str, practice_id: str, page: int, page_size: int
    ) -> dict[str, Any]:
        data = dict(self.config.get("form_params", {}))
        data.update(
            {
                "practice": "",
                "pageFilter": self.config["page_filter_type"],
                "pageFilterId": practice_id,
                "take": page_size,
                "skip": (page - 1) * page_size,
                "page": page,
                "pageSize": page_size,
                "searchId": "",
                "searchCount": 1,
            }
        )
        try:
            response = self.session.post(endpoint, data=data, timeout=DEFAULT_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ConnectorError(f"Simpson Thacher request failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise UnexpectedResponseError("Simpson Thacher returned non-object JSON")
        return payload

    def _parse_row(
        self, row: dict[str, Any], source_url: str, queried_practice: str
    ) -> PartnerEntryInfo:
        name = self._text(row.get("FullName"))
        role = self._text(row.get("Role"))
        slug = self._text(row.get("UrlName"))
        if not name or role.casefold() != "partner" or not slug:
            raise UnexpectedResponseError(
                "Simpson Thacher row is missing a name/URL or is not a Partner"
            )
        practices = self._labels(row.get("PracticeFocuses"))
        if queried_practice not in practices:
            practices.append(queried_practice)
        offices = self._labels(row.get("Office"))
        return PartnerEntryInfo(
            firm_key=self.firm_key,
            firm_name=self.config.get("name", ""),
            name=name,
            role=role,
            offices=offices,
            practices=practices,
            profile_url=urljoin(
                self.config["directory_url"], f"/our-team/partners/{slug}"
            ),
            source_url=source_url,
            source_record_id=self._text(row.get("Id") or row.get("ID")) or None,
        )

    @classmethod
    def _labels(cls, value: Any) -> list[str]:
        values = value if isinstance(value, list) else [value]
        labels: list[str] = []
        for item in values:
            if isinstance(item, dict):
                item = item.get("Text") or item.get("Name")
            text = cls._text(item)
            if text and text not in labels:
                labels.append(text)
        return labels

    @staticmethod
    def _text(value: Any) -> str:
        return " ".join(str(value or "").split())
