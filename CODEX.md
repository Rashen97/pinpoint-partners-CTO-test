# Pinpoint Partners CTO assessment

## Start here

This repository implements a recruiter-facing partner directory, a FastAPI backend, and a Python refresh pipeline backed by SQLite. The assessment brief sets a target of all Corporate and M&A partners across all offices at 15 named firms, within about six hours. It also asks for a runnable repository, an honest time-spent figure, and a credible plan for weekly operation and growth to 50 firms. The original PDF governs assessment requirements.

- [README.md](README.md) explains the product and the local run sequence.
- [DEVELOPMENT_PROCESS.md](DEVELOPMENT_PROCESS.md) records design decisions and alternatives.
- [ASSESSMENT_REVIEW.md](ASSESSMENT_REVIEW.md) covers the assessment criteria, the 15-firm coverage ledger, production plans, the commit-based time log, and AI use.
- [pipeline/firms.yaml](pipeline/firms.yaml) is the source registry. Use the current flags and source notes when checking what runs.

## Current implementation

- **Directory first.** Recruiters can search and filter, save partners in the browser, open firm-sourced profiles, and launch an editable Google search from the drawer. Recent changes shows recorded removals and offers a separate fictional preview. Additions and confirmed cross-firm moves require additional evidence and persistence. AI chat is deferred.
- **One refresh entry point.** `python -m pipeline.refresh` runs enabled connectors sequentially. Each connector returns `PartnerEntryInfo`. The pipeline normalises, deduplicates, validates, and updates the combined roster for the firms that pass. A failed or partial firm retains its prior verified entries and profiles. The command reports the failure and returns a nonzero status even when other firms update.
- **Separate profile enrichment.** The roster supplies eligible profile URLs. A shared HTML parser uses firm-specific selectors in `pipeline/profile_enrichment/profile_sources.yaml`. The default refresh enriches current entries for the firms verified in that run. A biography failure leaves roster membership intact.
- **SQLite and API ownership.** The pipeline owns migrations and writes to `database/partners.db`. The API reads it in read-only mode. Both `GET /api/partners` and `GET /api/partners/{partner_entry_id}` serve active records backed by `partner_profiles_all`, joined to `partner_entries_all` for identity and listing status. The coverage count describes the verified roster, and the list contains only partners with saved profiles.
- **Evidence and identity.** Entry IDs derive from the firm key and canonical profile URL. Only a verified refresh for that firm can mark a partner no longer listed. A change of profile URL or firm can produce a different ID. A name match alone gives insufficient evidence of a firm move.

## Run and verify locally

Run from the repository root in PowerShell. See the README for the complete setup.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s pipeline/tests
.\.venv\Scripts\python.exe -m pipeline.refresh --profile-limit 10
```

- `--profile-limit 10` runs the enabled directory connectors and caps enrichment across the firms verified in that run.
- `--directory-only` skips enrichment. `--firm <key>` diagnoses a single directory connector without publishing to the combined roster.
- The default local API is `127.0.0.1:8001`. The static frontend runs on `127.0.0.1:8080` and points to that API. Check the ports before starting a second process.
- A clean checkout needs a refresh before the connected UI has live profiles. The frontend guide also documents a standalone fictional preview.
- Keep credentials, browser cookies, raw profile captures, and generated SQLite files out of Git. Use small, sanitised fixtures for parser tests.

## Source coverage

The default refresh runs six verified firms plus Gibson Dunn with partial practice coverage. The frontend reports six verified firms and one with partial coverage. Counts are point-in-time observations. Consult SQLite or the API for current enrichment counts.

| Enabled firm | Verified source and scope | Observed entries |
| --- | --- | ---: |
| Paul Weiss | HTML directory results for Corporate and M&A, using the reported page markers | 216 |
| Cravath | Public partner search for Corporate and M&A, checked against reported totals | 65 |
| Milbank | Paginated attorney cards for Corporate, M&A, Distressed M&A, and explicit regional filters | 79 |
| Quinn Emanuel | Official M&A Litigation practice team, kept under its native label | 60 |
| Sullivan & Cromwell | General Practice (the firm's Corporate group) and both explicit M&A filters, sorted by source ID for stable pagination | 155 |
| Davis Polk | All 22 published Corporate practice groups, including M&A, with all offices selected | 190 |

Simpson Thacher’s connector now uses the current public staff-listing API. Both practice filters returned distinct pages, but the full Corporate run hit HTTP 429 after 20 pages. Keep the firm disabled until a paced run verifies both complete rosters and the current profile selectors. Kirkland’s direct directory request returned HTTP 403. Wachtell stays disabled because its Corporate request returned HTTP 403 from the Python runner. The parser extracted 34 Corporate partners from 122 role-labelled rows in a browser capture. A saved capture verifies the parser, and a repeatable live source is required for automatic refresh. If a Davis Polk practice fails validation in a future run, its explicit partial setting preserves the last verified roster while publishing observed data. Refer to the assessment review for all remaining firms and the evidence behind each status.

Gibson Dunn's connector follows the WP Grid Builder load-more control and verified 278 partners across M&A, Capital Markets, Private Equity, Finance, and Investment Funds. The firm’s London training materials support the additional groups. Its full global Corporate scope remains unverified. Latham’s Coveo configuration is a lead for checking the directory request. Quinn Emanuel’s general directory POST capture demonstrated HTML attorney cards and paging. The implemented connector uses the separate M&A Litigation practice-team endpoint.

When verifying a new source, distinguish directory discovery, a successful test request, complete roster coverage, and successful profile enrichment. Check the site's access rules, use public requests, and stop on persistent access blocks. Inspect the actual query, request body, and response together. Keep firm-native practice labels and document the scope decision when a label is ambiguous.

## Production priorities

- Run the existing CLI weekly through an orchestrator such as Google Cloud Composer, with a persistent database accessible to the job and API, overlap protection, per-firm history, and failure alerts. Scheduling and visible per-firm freshness are planned.
- Build and evaluate bulk onboarding from a firm name and optional homepage. Discover candidate directories and profile links, reuse common extraction patterns, and check sample results. Review practice scope and completeness before enabling a firm.
- Record first sightings after each firm's verified baseline. Require corroborating evidence before presenting a confirmed cross-firm move.
- Before handoff, verify the clean-checkout run path and report actual coverage, enrichment, and known failures separately. Describe proposed work as planned.


## Refresh reliability refinement

- publish_partial_scope controls whether complete limited-scope
  extractions may be published.
- expected_partial_scope controls whether partial coverage is an
  accepted operational outcome.
- Unexpected partial coverage returns a nonzero exit code during
  the default refresh while still publishing eligible observations.
- Failed or incomplete extractions are rejected.
- Partial publication does not infer removals or overwrite previously
  verified roster entries.
- The latest regression suite contains 34 passing tests.

Historical count anomaly detection, visible per-firm freshness and
scheduled production execution remain planned improvements.
