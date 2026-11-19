"""Sullivan & Cromwell public Solr directory connector."""

from __future__ import annotations

import math
from typing import Any
from urllib.parse import urljoin

import requests

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo


class SullivanCromwellConnector(Connector):
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
        practice_filters = self.config.get("practice_filters", [])
        if not endpoint or not practice_filters:
            raise ConnectorError("Sullivan & Cromwell endpoint or practice filters are missing")

        records_by_url: dict[str, PartnerEntryInfo] = {}
        pages_fetched = 0
        for practice in practice_filters:
            records, page_count = self._extract_practice(
                endpoint, str(practice["id"]), str(practice["label"])
            )
            pages_fetched += page_count
            for record in records:
                existing = records_by_url.get(record.profile_url)
                if existing is None:
                    records_by_url[record.profile_url] = record
                else:
                    existing.practices.extend(
                        label for label in record.practices if label not in existing.practices
                    )

        covered = [str(item["label"]) for item in practice_filters]
        missing = list(self.config.get("missing_practices", []))
        return ExtractionResult(
            firm_key=self.firm_key,
            records=list(records_by_url.values()),
            pages_fetched=pages_fetched,
            extraction_complete=True,
            scope_verified=not missing,
            covered_practices=covered,
            missing_practices=missing,
            warnings=(
                ["No broad native Corporate directory filter has been verified."]
                if missing
                else []
            ),
        )

    def _extract_practice(
        self, endpoint: str, practice_id: str, practice_label: str
    ) -> tuple[list[PartnerEntryInfo], int]:
        page_size = int(self.config.get("page_size", 100))
        first_payload = self._fetch(endpoint, practice_id, 0, page_size)
        response = self._response(first_payload, practice_label)
        total = int(response.get("numFound", 0))
        if total <= 0:
            raise UnexpectedResponseError(
                f"Sullivan & Cromwell {practice_label} returned an empty roster"
            )
        page_count = math.ceil(total / page_size)
        records: list[PartnerEntryInfo] = []
        for page_number in range(page_count):
            payload = first_payload if page_number == 0 else self._fetch(
                endpoint, practice_id, page_number * page_size, page_size
            )
            docs = self._response(payload, practice_label).get("docs")
            if not isinstance(docs, list) or not docs:
                raise UnexpectedResponseError(
                    f"Sullivan & Cromwell {practice_label} page {page_number + 1} has no rows"
                )
            records.extend(
                self._parse_doc(doc, endpoint, practice_label)
                for doc in docs
                if isinstance(doc, dict)
            )

        unique = {record.profile_url: record for record in records}
        if len(records) != total or len(unique) != total:
            raise UnexpectedResponseError(
                f"Sullivan & Cromwell {practice_label} reported {total} but parsed "
                f"{len(records)} rows and {len(unique)} unique profiles"
            )
        return list(unique.values()), page_count

    def _fetch(
        self, endpoint: str, practice_id: str, start: int, rows: int
    ) -> dict[str, Any]:
        params = [
            ("q", "*:*"),
            ("wt", "json"),
            ("start", str(start)),
            ("rows", str(rows)),
            (
                "fl",
                "id,title,custom_s_proftype,custom_s_office_title,custom_s_url",
            ),
            ("fq", "custom_s_type:Lawyer"),
            ("fq", f"custom_is_practices:{practice_id}"),
            ("fq", f"custom_i_type:{self.config['partner_type_id']}"),
        ]
        try:
            response = self.session.get(endpoint, params=params, timeout=DEFAULT_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ConnectorError(f"Sullivan & Cromwell request failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise UnexpectedResponseError("Sullivan & Cromwell returned non-object JSON")
        return payload

    @staticmethod
    def _response(payload: dict[str, Any], practice: str) -> dict[str, Any]:
        response = payload.get("response")
        if not isinstance(response, dict):
            raise UnexpectedResponseError(
                f"Sullivan & Cromwell {practice} JSON has no response object"
            )
        return response

    def _parse_doc(
        self, doc: dict[str, Any], source_url: str, practice: str
    ) -> PartnerEntryInfo:
        name = self._text(doc.get("title"))
        role = self._text(doc.get("custom_s_proftype"))
        href = self._text(doc.get("custom_s_url"))
        if not name or role.casefold() != "partner" or not href:
            raise UnexpectedResponseError(
                "Sullivan & Cromwell row is missing a name/profile URL or is not a Partner"
            )
        office = self._text(doc.get("custom_s_office_title"))
        return PartnerEntryInfo(
            firm_key=self.firm_key,
            firm_name=self.config.get("name", ""),
            name=name,
            role=role,
            offices=[office] if office else [],
            practices=[practice],
            profile_url=urljoin(self.config["directory_url"], href),
            source_url=source_url,
            source_record_id=self._text(doc.get("id")) or None,
        )

    @staticmethod
    def _text(value: Any) -> str:
        return " ".join(str(value or "").split())
