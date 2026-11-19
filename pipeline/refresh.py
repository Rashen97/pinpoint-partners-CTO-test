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
from pipeline.models import ExtractionResult, PartnerEntryInfo
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
        "--publish-partial",
        action="store_true",
        help="Publish and enrich a complete limited-scope extraction for one --firm",
    )
    parser.add_argument(
        "--directory-only",
        action="store_true",
        help="Stop after directory extraction (development/debugging only)",
    )
    parser.add_argument(
        "--profile-limit",
        type=int,
        help="Only enrich the first N profiles eligible for publication in this run",
    )
    args = parser.parse_args()
    if args.publish_partial and not args.firm:
        parser.error("--publish-partial requires --firm")
    return args


def refresh_firm(
    firm_key: str,
    config: dict[str, Any],
    args: argparse.Namespace,
    database: SQLiteDatabase,
) -> tuple[dict[str, Any], int, ExtractionResult | None]:
    try:
        connector = build_connector(firm_key, config)
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
    elif args.publish_partial or (not args.firm and config.get("publish_partial_scope") is True):
        payload["status"] = "partial"

        if args.publish_partial or config.get("expected_partial_scope") is True:
            return payload, 0, result

        payload["status"] = "unexpected_partial"
        return payload, 2, result
    elif not args.include_unverified_scope:
        payload["status"] = "scope_unverified"
        return payload, 2, None

    payload["status"] = "complete" if result.scope_verified else "partial"
    return payload, 0 if result.scope_verified else 2, verified_result


def refresh_profiles(
    database: SQLiteDatabase,
    entries: list[PartnerEntryInfo],
    args: argparse.Namespace,
    source: str,
) -> tuple[dict[str, Any], int]:
    if args.directory_only:
        return {"status": "skipped", "reason": "--directory-only", "source": source, "database": None}, 0
    profile_connector = ConfiguredHtmlProfileConnector(load_profile_sources())
    enrichment = enrich_entries(entries, profile_connector, limit=args.profile_limit)
    profiles_path = database.save_all_partner_profiles(
        enrichment.profiles, enrichment.failures, firm_key=args.firm
    )
    return {
        "status": "partial" if enrichment.failures else "complete",
        "source": source,
        "database": str(profiles_path),
        "failures_table": "partner_profile_failures_all",
        "input_count": len(entries),
        "attempted_count": len(enrichment.profiles) + len(enrichment.failures),
        "profile_count": len(enrichment.profiles),
        "failure_count": len(enrichment.failures),
    }, 3 if enrichment.failures else 0


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
    partial_results: list[ExtractionResult] = []
    exit_codes: list[int] = []
    for firm_key in firm_keys:
        payload, exit_code, result = refresh_firm(
            firm_key,
            firms[firm_key],
            args,
            database,
        )
        firm_payloads[firm_key] = payload
        exit_codes.append(exit_code)
        if result is not None:
            (verified_results if result.scope_verified else partial_results).append(result)

    if args.firm:
        target = firm_payloads[args.firm]
        target["database"]["path"] = str(database.path)
        target["profile_enrichment"] = {
            "status": "skipped",
            "reason": "Profile enrichment consumes the combined partner_entries_all table",
        }
        if partial_results:
            result = partial_results[0]
            source = database.save_partial_partner_entries(result)
            target["database"]["all_partner_entries"] = source
            target["profile_enrichment"], code = refresh_profiles(database, result.records, args, source)
            print(json.dumps(target, indent=2, ensure_ascii=False))
            return code
        print(json.dumps(target, indent=2, ensure_ascii=False))
        return exit_codes[0]

    combined_path = None
    if verified_results:
        combined_path = database.save_all_partner_entries(verified_results)
    for result in partial_results:
        combined_path = database.save_partial_partner_entries(result)

    profile_output: dict[str, Any]
    profile_exit_code = 0
    if combined_path is None:
        profile_output = {
            "status": "skipped",
            "reason": "No firm produced a roster eligible for publication",
            "source": None,
            "database": None,
        }
    elif args.directory_only:
        profile_output, profile_exit_code = refresh_profiles(database, [], args, combined_path)
    else:
        verified_firm_keys = {result.firm_key for result in verified_results}
        partial_entry_ids = {
            entry.partner_entry_id for result in partial_results for entry in result.records
        }
        unified_entries = [
            entry for entry in database.load_all_partner_entries()
            if entry.firm_key in verified_firm_keys or entry.partner_entry_id in partial_entry_ids
        ]
        profile_output, profile_exit_code = refresh_profiles(database, unified_entries, args, combined_path)

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
    if any(exit_codes):
        if combined_path is None:
            print("Combined dataset was not replaced.", file=sys.stderr)
        else:
            print("Updated eligible firms and kept prior records for the other firms.", file=sys.stderr)
        for (firm_key, payload), exit_code in zip(firm_payloads.items(), exit_codes):
            if exit_code:
                details = payload.get("error") or "; ".join(payload.get("warnings", []))
                message = f"{firm_key}: {payload['status']}"
                print(f"{message} ({details})" if details else message, file=sys.stderr)
    return max([*exit_codes, profile_exit_code], default=0)


if __name__ == "__main__":
    raise SystemExit(main())
