# Pinpoint Partner Intelligence

## Purpose and users

Build a locally runnable market intelligence tool for recruiters at Pinpoint Partners. Recruiters use it to map the partner market and prepare for outreach. The tracked law firms are employers. The tool provides a searchable, source-backed directory of Corporate and M&A partners, shows when the information was checked, and highlights changes between weekly rosters.

## Product requirements

- Cover the 15 firms listed under Source Evidence, across all offices. Design the onboarding and refresh workflow so coverage can grow to about 50 firms.
- Include partners whose firm directory or profile establishes Corporate or M&A practice membership. Exclude associates, counsel, and retired partners. Use firm sources to resolve ambiguous titles and document inclusion decisions.
- Preserve published role, office, and practice labels, including multiple offices or practice memberships. Document ambiguous practice labels and the evidence for including them. Quinn Emanuel's M&A and Corporate Governance Litigation labels describe adjacent litigation work and require an explicit coverage note.
- Deduplicate overlapping searches by firm and canonical public profile URL. Merge office and practice values from validated records. Use public firm sources to resolve practice membership and identity. Keep cross-firm records separate unless credible evidence supports a link.
- Let recruiters search by name, filter by firm, office, and practice, and open a partner profile with published facts, bio information where available, source links, and freshness dates.
- Show firm-by-firm coverage and a weekly change view. Distinguish the latest refresh attempt from the most recent validated data.
- Keep CRM replacement and a deployed scheduler outside the initial scope. Provide a refresh command that can be run weekly with a local scheduler. Keep agentic crawling, vector storage, MCP servers, and Vertex or Agent Search indexing outside the initial scope.
- Prioritize directory coverage and reliable refreshes before profile Q&A. If added, ground answers in saved source content, cite sources and dates, identify missing evidence, and label suggested call openers as suggestions. The directory and refresh must work without AI or GCP credentials.

## Repository and implementation status

| Area | Current state and intended responsibility |
|---|---|
| `backend/app/core/config.py` | Resolves `DATABASE_URL` and defaults to the repository-local `data/pinpoint.db`. Creates the parent directory for file-backed SQLite. |
| `backend/app/db/` | Provides the SQLAlchemy declarative base, engine, session factory, and `get_db()` dependency. SQLite connections enforce foreign keys. Schema models and the first Alembic migration are pending. |
| `backend/app/api/`, `repositories/`, `services/` | Backend structure for the planned FastAPI routes and schemas, data access, and application logic. |
| `pipeline/connectors/`, `services/`, `storage/` | Scaffolding for firm-specific collection, refresh orchestration, validation, and persistence. |
| `frontend/` | Reserved for the recruiter-facing directory. |
| `tests/unit/backend/test_database_connection.py` | Verifies the configured database connection can execute `SELECT 1`. |
| `pyproject.toml` | Defines Python 3.11+, SQLAlchemy, Alembic, and the pytest development extra. |

Use SQLAlchemy and Alembic for shared persistence and schema evolution. SQLite supports local development without a separate database server. FastAPI, the directory UI, collectors, and refresh commands are planned. Add dependencies to `pyproject.toml` as the implementation uses them.

## Data and refresh requirements

Firm-specific connectors should emit a common record shape. The refresh workflow should manage observation timestamps and per-firm status.

| Field | Meaning |
|---|---|
| `firm` | Stable firm identifier |
| `name` | Published name |
| `role` | Published role or title |
| `offices` | Firm-listed offices |
| `practice_labels` | Native firm practice labels |
| `profile_url` | Canonical public profile URL and, with `firm`, the unique key |
| `source_url` | Public roster or directory used as evidence |
| `first_seen_at` | First validated observation |
| `last_seen_at` | Most recent validated observation of the partner |
| `last_checked_at` | Latest relevant check attempt, distinct from a successful observation |

- Record each firm's attempt status, timestamps, counts, and diagnostic details. Expose coverage as verified, partial, blocked, not implemented, or needs browser verification as appropriate.
- Fetch and validate all required practice searches and pages before publishing a new firm roster. Treat blocked, incomplete, unexpectedly empty, or anomalously small results as failed validation. Preserve the last validated roster and surface the latest attempt status.
- Publish validated roster updates and their change records together. Repeating a refresh must preserve existing identities and avoid duplicate records or duplicate change events.
- Compare consecutive validated, complete rosters. Label presence changes as `newly listed` and `no longer listed`. The first validated snapshot establishes the baseline. Roster presence alone does not establish employment history.
- Run profile enrichment separately from weekly roster collection. Preserve evidence URLs and check dates. Regenerate optional AI briefs only when their source content changes.
- Keep credentials, cookies, raw browser sessions, per-request identifiers, local databases, and generated data out of Git. Use sanitized fixtures.

## Implementation sequence

1. Add schema models and the initial Alembic migration. Define the partner identity constraint and persistence for refresh attempts, validated observations, and changes.
2. Implement the Paul, Weiss smoke test below, then verify full Corporate and M&A pagination and overlapping results.
3. Add a second connector with a different response shape before extracting shared fetch, validation, storage, logging, and change-detection logic. Keep response parsing in each connector.
4. Add firm-by-firm coverage and expand collectors using the source notes. Verify source filters, end-of-pagination behavior, and canonical profile URLs for each firm.
5. Implement the API and recruiter directory, including filters, profile detail, freshness, and weekly changes. Document the implemented refresh commands and how to run them weekly.

### Planned refresh interface

Support refreshing all configured firms by default, refreshing one firm by its stable identifier, and running all firms explicitly. The proposed invocation is:

```bash
python refresh.py
python refresh.py --firm paul_weiss
python refresh.py --all
```

### Paul, Weiss smoke test

Start with one Paul, Weiss M&A page:

1. Fetch the confirmed endpoint.
2. Parse partner names and profile links.
3. Save validated rows to SQLite.
4. Run the refresh twice.
5. Confirm no duplicate rows are added.

The endpoint is:

```text
https://www.paulweiss.com/umbraco/surface/lawyerssearch/GetLawyersResult
```

Use separate requests for Corporate and M&A:

```text
pageId=1492
pageSize=12
pagingNumber=1
position=Partner
industries=All
offices=All
schools=All
lastname=All
searchText=All
```

The public filter label uses `&` for M&A, while the captured request value spells out `and`.

Do not call this initial page a production roster. Next:

- Verify pagination.
- Add the Corporate search.
- Deduplicate by `(firm, profile_url)`.
- Merge practice labels.
- Implement a second adapter with a different response shape.

## Source Evidence

Initial source observations from 18 November 2026. The table defines the 15-firm scope. Counts, endpoints, and filters are dated observations and should be revalidated before relying on them.

| Firm | Source status | Initial evidence and follow-up |
|---|---|---|
| Paul, Weiss | Tested HTML endpoint | Corporate and M&A pages 1/2 tested; verify remaining pagination and profile URL pattern before broad claims |
| Sullivan & Cromwell | Tested JSON GET | M&A and Partner search returned 94 hits; inspect fields and page with `start`/`rows`; Corporate filter remains unverified |
| Kirkland & Ellis | JSON pattern captured | Letter-based JSON endpoint captured; exact practice/role filters and all-letter coverage remain to be confirmed |
| Wachtell, Lipton, Rosen & Katz | HTML captured | Corporate + Partner + View All source; direct Python 403 needs browser verification; no general M&A option in the captured dropdown |
| Quinn Emanuel | POST/HTML captured | Attorney cards expose name, title, office, and profile URL; role/practice filtering and pagination remain unverified |
| Davis Polk | Algolia POST captured | Partner search returned 211 hits; practice filter, full pagination, and M&A coverage remain unverified |
| Simpson Thacher | Form POST/JSON captured | Team response exposes partner role, office, practice, and URL name; Corporate/M&A IDs and pagination remain unverified |
| Gibson, Dunn | HTTP 200 captured; pagination uncertain | Initial request returned 20 profile links; `?_paged=2` repeated results; capture WP Grid Builder pagination |
| Latham & Watkins | Public 200; no static rows | Coveo source identified, but the actual lawyer request and practice filter are unverified |
| Cravath | 403 from direct fetch | Indexed Partner/Corporate view exists; capture View All and practice filter in a browser |
| Milbank | 403 from direct fetch | Corporate and M&A filters exist; capture browser requests rather than inferring IDs |
| Paul Hastings | GET 200; no static profile anchors | Capture practice, role, and next-page requests |
| Skadden | 403 from direct fetch | M&A-filtered URL and View More exist; capture Position and pagination requests |
| King & Spalding | 403 from direct fetch | Official M&A View All link exists; capture actual results request |
| Weil | 403 from direct fetch | Use public practice/capability and role filters; verify the M&A page is not only Key Contacts |

### Paul, Weiss

Directory:

```text
https://www.paulweiss.com/professionals
```

Profile links use `/professionals/partners-and-counsel/`. A response may include the same link more than once. Verify title and practice rather than relying on URL text.

### Sullivan & Cromwell

Directory:

```text
https://www.sullcrom.com/LawyerListing
```

Verified public search endpoint:

```text
https://searchg2.crownpeak.net/sullivancromwell-sullcrom-live/select/
```

Use repeated `fq` parameters rather than a dict that overwrites values.

Relevant captured fields include:

```text
custom_s_type:Lawyer
custom_is_practices:69620
custom_i_type:25257
```

The M&A test returned 94 records, but pagination fields and complete profile metadata still require verification.

### Kirkland & Ellis

Directory:

```text
https://www.kirkland.com/lawyers
```

Endpoint pattern:

```text
https://www.kirkland.com/api/sitecore/ProfessionalsApi/Lawyers?letter=A
```

JSON fields may include `Name`, `Position`, `Offices`, `Url`, and `Description`. Confirm practice/role filtering and whether letters provide complete coverage.

### Wachtell, Lipton, Rosen & Katz

Directory:

```text
https://www.wlrk.com/attorneys/
```

The captured HTML showed Corporate, Partner, and View All controls. The 286 distinct profile links do not prove that the 286 profiles are in Corporate or M&A. Browser verification is required. Real Estate M&A is not a substitute for general M&A.

### Quinn Emanuel

Directory:

```text
https://www.quinnemanuel.com/attorneys
```

Captured endpoint:

```text
https://www.quinnemanuel.com/Umbraco/surface/AttorneysListSurface/GetAttorneyListByFilter
```

The endpoint is an HTTP POST with query parameters in the captured request. Check Headers, Payload, and Response before implementation. HTML cards use `.attorney-card`, `h3 a`, `.designation`, and `.location a`.

### Davis Polk

Directory:

```text
https://www.davispolk.com/lawyers
```

Captured Algolia endpoint:

```text
https://dbc8kua830-dsn.algolia.net/1/indexes/*/queries
```

The captured Partner-only response is not sufficient to establish M&A or Corporate coverage. Do not commit the captured search credential or per-request identifier. Capture practice facets or prefer the official M&A team page if it is complete.

### Simpson Thacher

Directory:

```text
https://www.stblaw.com/our-team
```

Captured endpoint:

```text
https://www.stblaw.com/dataservices/DataServices.Content.Services.Json.AttorneyLookup/TeamMembers
```

The request is an HTTP POST with a URL-encoded form body. Verify the Corporate/M&A practice IDs and page 2 behavior. Check each row's role; Counsel and Partners may be grouped. Profile URL format:

```text
https://www.stblaw.com/our-team/partners/{UrlName}
```

Do not hardcode a captured search ID.

## Request and Parsing Rules

A browser Request URL is only one part of the request:

- GET query strings belong in `params`
- POST query strings belong in `params` unless DevTools shows them as form data
- HTML form bodies belong in `data`
- JSON bodies belong in `json`
- Inspect Headers, Payload, and Response together

Rules:

- Reproduce the public directory's own role and practice filters.
- Establish the end of pagination.
- Parse the returned response body.
- Prefer browser automation only when the public source requires JavaScript and automation is permitted.
- Treat a plain-Python 403 as a failed source test, not evidence that the directory is empty.
- Sanitize fixtures and never commit raw sessions or credentials.

## Local setup and checks

Run from the repository root on Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

On macOS or Linux, use `python3 -m venv .venv` and `source .venv/bin/activate`, then run the same install and test commands. Set `DATABASE_URL` before starting the process to override the default. Relative SQLite paths resolve from the working directory. The connection test checks connectivity. Schema initialization depends on the first migration.

## Development verification

- Install the project in a clean environment and run the documented tests.
- Verify that the Paul, Weiss smoke test persists names and URLs. Confirm distinct pagination batches and preservation of native practice labels across overlapping results.
- Exercise HTML and JSON parsers with sanitized fixtures. Verify that an identical rerun creates no duplicate partner records or change events.
- Verify that failed and partial refreshes preserve the last validated roster and show the latest check status. Check first-snapshot behavior and changes between complete snapshots.
- Verify directory search and filters, profile evidence and freshness, and the weekly changes view once implemented.
- Keep the README aligned with actual setup, refresh, and scheduling commands. Document architecture decisions, deliberate omissions, and how to onboard firms. Record source coverage and remaining gaps with their evidence.
