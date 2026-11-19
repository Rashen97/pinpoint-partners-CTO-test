"""Orchestrate all viable directory connectors and profile enrichment."""

# Run these commands from the repository root in PowerShell.
#
# Show CLI options.
# .\.venv\Scripts\python.exe -m pipeline.refresh --help
#
# Refresh all enabled firms.
# .\.venv\Scripts\python.exe -m pipeline.refresh
#
# Extract full directories and enrich up to 10 profiles from the combined roster.
# .\.venv\Scripts\python.exe -m pipeline.refresh --profile-limit 10
#
# Extract directories for all enabled firms and skip profile enrichment.
# .\.venv\Scripts\python.exe -m pipeline.refresh --directory-only
#
# Refresh a single firm.
# .\.venv\Scripts\python.exe -m pipeline.refresh --firm paul_weiss
# .\.venv\Scripts\python.exe -m pipeline.refresh --firm simpson_thacher
#
# Extract a single firm without running the combined enrichment stage.
# .\.venv\Scripts\python.exe -m pipeline.refresh --firm paul_weiss --directory-only
#
# Inspect a targeted partial roster.
# .\.venv\Scripts\python.exe -m pipeline.refresh --firm sullivan_cromwell --include-unverified-scope
#
# Diagnose a connector whose live source may fail.
# .\.venv\Scripts\python.exe -m pipeline.refresh --firm kirkland

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any

from pipeline.config import load_firms
from pipeline.connectors import build_connector
from pipeline.connectors.errors import ConnectorError
from pipeline.models import ExtractionResult
from pipeline.processing.deduplicate import deduplicate_records
from pipeline.processing.normalize import normalize_records
from pipeline.profile_enrichment import (
    ConfiguredHtmlProfileConnector,
    enrich_entries,
    load_profile_sources,
)
from pipeline.storage.sqlite_database import SQLiteDatabase


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh all currently viable firm connectors"
    )
    parser.add_argument(
        "--firm",
        help="Run one firm key instead of every refresh-enabled firm",
    )
    parser.add_argument(
        "--include-unverified-scope",
        action="store_true",
        help="Report a targeted scope-unverified extraction as partial",
    )
    parser.add_argument(
        "--directory-only",
        action="store_true",
        help="Stop after directory extraction (development/debugging only)",
    )
    parser.add_argument(
        "--profile-limit",
        type=int,
        help="Only enrich the first N profiles in the combined roster",
    )
    return parser.parse_args()


def refresh_firm(
    firm_key: str,
    config: dict[str, Any],
    args: argparse.Namespace,
    database: SQLiteDatabase,
) -> tuple[dict[str, Any], int, ExtractionResult | None]:
    connector = build_connector(firm_key, config)
    try:
        result = connector.extract()
    except (ConnectorError, NotImplementedError) as exc:
        return (
            {
                "firm_key": firm_key,
                "status": "failed",
                "error": str(exc),
                "database": {
                    "connector_extraction": None,
                    "partner_entries": None,
                },
            },
            1,
            None,
        )

    connector_path = database.save_connector_extraction(result)
    result.records = deduplicate_records(normalize_records(result.records))
    payload = asdict(result)
    payload["status"] = "extracted"
    payload["database"] = {
        "connector_extraction": str(connector_path),
        "partner_entries": None,
    }

    if not result.extraction_complete or not result.records:
        payload["status"] = "incomplete"
        return payload, 1, None

    verified_result: ExtractionResult | None = None
    if result.scope_verified:
        entries_path = database.save_partner_entries(result)
        payload["database"]["partner_entries"] = str(entries_path)
        verified_result = result
    elif not args.include_unverified_scope:
        payload["status"] = "scope_unverified"
        return payload, 2, None

    payload["status"] = "complete" if result.scope_verified else "partial"
    return payload, 0 if result.scope_verified else 2, verified_result


def main() -> int:
    args = parse_args()
    firms = load_firms()
    if args.firm:
        if args.firm not in firms:
            available = ", ".join(sorted(firms))
            raise SystemExit(f"Unknown firm '{args.firm}'. Available firms: {available}")
        firm_keys = [args.firm]
    else:
        firm_keys = [
            firm_key
            for firm_key, config in firms.items()
            if config.get("refresh_enabled") is True
        ]
        if not firm_keys:
            raise SystemExit("No refresh-enabled firms are configured")

    database = SQLiteDatabase()
    firm_payloads: dict[str, dict[str, Any]] = {}
    verified_results: list[ExtractionResult] = []
    exit_codes: list[int] = []
    for firm_key in firm_keys:
        payload, exit_code, verified_result = refresh_firm(
            firm_key,
            firms[firm_key],
            args,
            database,
        )
        firm_payloads[firm_key] = payload
        exit_codes.append(exit_code)
        if verified_result is not None:
            verified_results.append(verified_result)

    if args.firm:
        firm_payloads[args.firm]["database"]["path"] = str(database.path)
        firm_payloads[args.firm]["profile_enrichment"] = {
            "status": "skipped",
            "reason": "Profile enrichment consumes the combined partner_entries_all table",
        }
        print(json.dumps(firm_payloads[args.firm], indent=2, ensure_ascii=False))
        return exit_codes[0]

    combined_path = None
    if len(verified_results) == len(firm_keys):
        combined_path = database.save_all_partner_entries(verified_results)

    profile_output: dict[str, Any]
    profile_exit_code = 0
    if combined_path is None:
        profile_output = {
            "status": "skipped",
            "reason": "The combined partner-entry dataset was not replaced",
            "source": None,
            "database": None,
        }
    elif args.directory_only:
        profile_output = {
            "status": "skipped",
            "reason": "--directory-only",
            "source": str(combined_path),
            "database": None,
        }
    else:
        unified_entries = database.load_all_partner_entries()
        profile_connector = ConfiguredHtmlProfileConnector(load_profile_sources())
        enrichment = enrich_entries(
            unified_entries,
            profile_connector,
            limit=args.profile_limit,
        )
        profiles_path = database.save_all_partner_profiles(
            enrichment.profiles,
            enrichment.failures,
        )
        profile_output = {
            "status": "complete" if not enrichment.failures else "partial",
            "source": str(combined_path),
            "database": str(profiles_path),
            "failures_table": "partner_profile_failures_all",
            "input_count": len(unified_entries),
            "attempted_count": (
                len(unified_entries)
                if args.profile_limit is None
                else min(len(unified_entries), args.profile_limit)
            ),
            "profile_count": len(enrichment.profiles),
            "failure_count": len(enrichment.failures),
        }
        if enrichment.failures:
            profile_exit_code = 3

    output = {
        "mode": "all",
        "selected_firms": firm_keys,
        "summary": {
            firm_key: {
                "status": payload["status"],
                "record_count": len(payload.get("records", [])),
            }
            for firm_key, payload in firm_payloads.items()
        },
        "database": {
            "path": str(database.path),
            "all_partner_entries": str(combined_path) if combined_path else None,
        },
        "profile_enrichment": profile_output,
        "firms": firm_payloads,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    if combined_path is None:
        print("Combined dataset was not replaced.", file=sys.stderr)
        for firm_key, payload in firm_payloads.items():
            if payload["status"] != "complete":
                details = payload.get("error") or "; ".join(payload.get("warnings", []))
                message = f"{firm_key}: {payload['status']}"
                print(f"{message} ({details})" if details else message, file=sys.stderr)
    return max([*exit_codes, profile_exit_code], default=0)


if __name__ == "__main__":
    raise SystemExit(main())
