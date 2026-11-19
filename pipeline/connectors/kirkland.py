"""Kirkland & Ellis lawyer-directory connector.

The captured endpoint iterates by surname initial and returns JSON lawyer rows.
The exact Corporate/M&A filter is not yet verified, so this connector extracts
Partner rows but deliberately marks its practice scope as unverified.
"""

from __future__ import annotations

import string
from collections.abc import Iterable
from typing import Any
from urllib.parse import urljoin

import requests

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo


class KirklandConnector(Connector):
    ROW_KEYS = ("Results", "Lawyers", "Items", "results", "lawyers", "items")

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
            raise ConnectorError("Kirkland results_url is missing")

        records_by_url: dict[str, PartnerEntryInfo] = {}
        pages_fetched = 0

        for letter in string.ascii_uppercase:
            rows = self._fetch_letter(endpoint, letter)
            pages_fetched += 1
            for row in rows:
                record = self._parse_row(row, endpoint)
                if record is not None:
                    records_by_url[record.profile_url] = record

        return ExtractionResult(
            firm_key=self.firm_key,
            records=list(records_by_url.values()),
            pages_fetched=pages_fetched,
            extraction_complete=True,
            scope_verified=False,
            missing_practices=["Corporate", "Mergers and Acquisitions"],
            warnings=[
                "The captured source has no verified Corporate/M&A filter yet.",
                "Records are exact Partner-role matches only; do not load this as the in-scope roster.",
            ],
        )

    def _fetch_letter(self, endpoint: str, letter: str) -> list[dict[str, Any]]:
        try:
            response = self.session.get(
                endpoint,
                params={"letter": letter},
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ConnectorError(
                f"Kirkland request for letter {letter} failed: {exc}"
            ) from exc

        content_type = response.headers.get("Content-Type", "").lower()
        if "json" not in content_type:
            raise UnexpectedResponseError(
                f"Kirkland letter {letter} returned {content_type or 'an unknown content type'}, not JSON"
            )
        try:
            payload = response.json()
        except requests.exceptions.JSONDecodeError as exc:
            raise UnexpectedResponseError(
                f"Kirkland letter {letter} returned invalid JSON"
            ) from exc
        return self._find_rows(payload, letter)

    def _find_rows(self, payload: Any, letter: str) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            rows = next(
                (payload[key] for key in self.ROW_KEYS if isinstance(payload.get(key), list)),
                None,
            )
        else:
            rows = None

        if rows is None or not all(isinstance(row, dict) for row in rows):
            raise UnexpectedResponseError(
                f"Kirkland letter {letter} JSON did not contain a recognized row list"
            )
        return rows

    def _parse_row(
        self, row: dict[str, Any], source_url: str
    ) -> PartnerEntryInfo | None:
        role = self._text(row.get("Position"))
        if role.casefold() != "partner":
            return None

        name = self._text(row.get("Name"))
        relative_url = self._text(row.get("Url"))
        if not name or not relative_url:
            raise UnexpectedResponseError("Kirkland Partner row is missing Name or Url")

        return PartnerEntryInfo(
            firm_key=self.firm_key,
            name=name,
            role=role,
            offices=self._string_list(row.get("Offices")),
            practices=self._string_list(
                row.get("Practices") or row.get("PracticeAreas") or row.get("Services")
            ),
            profile_url=urljoin(self.config["directory_url"], relative_url),
            source_url=source_url,
            firm_name=self.config.get("name", ""),
        )

    @staticmethod
    def _text(value: Any) -> str:
        return " ".join(str(value or "").split())

    @classmethod
    def _string_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        values: Iterable[Any] = value if isinstance(value, list) else [value]
        cleaned: list[str] = []
        for item in values:
            if isinstance(item, dict):
                item = item.get("Name") or item.get("Title") or item.get("Text")
            text = cls._text(item)
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned
