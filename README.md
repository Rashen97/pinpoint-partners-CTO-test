# Pinpoint partner directory

Pinpoint’s recruiters need to prepare for calls with individual partners and keep up with changes across law firms. This project gives them a searchable directory of Corporate and M&A partners, with filters for firm, office, and practice. Recruiters can save a shortlist in their browser, read a source-backed profile, and open an editable Google search for recent deals, press coverage, or firm announcements.

The directory is the starting point because recruiters can scan a market segment and open a profile in the same workflow. Recent changes shows recorded removals and includes a labelled fictional preview of additions and removals. The prototype leaves AI chat, shared shortlists, and cross-firm move detection for later.

The pipeline uses Python connectors to collect and validate firm rosters, then enriches the partner profiles. SQLite keeps both stages in a single local database. FastAPI exposes the enriched directory and profile details through a typed API, and the browser interface runs without a frontend build step.


## Architecture and engineering decisions

The system follows a modular monolith approach, separating data collection,
validation, storage, profile enrichment, the API, and the recruiter interface.

Firm websites
    -> Directory connectors
    -> Normalisation, deduplication and validation
    -> SQLite roster storage
    -> Profile enrichment
    -> FastAPI
    -> Recruiter directory

| Technology | Reason for choosing it |
| --- | --- |
| Python | Suitable for HTTP requests, HTML parsing, data processing and automated testing. |
| YAML | Keeps firm-specific source configuration separate from the refresh logic. |
| SQLite | Provides transactional storage and relational queries without requiring a separate database service. |
| FastAPI | Provides typed API responses, automatic validation and interactive API documentation. |
| HTML, CSS and JavaScript | Delivers a lightweight recruiter interface without introducing a frontend build process. |
| unittest | Supports repeatable regression testing without additional testing dependencies. |

### Alternatives considered

- JSON storage was used initially but replaced with SQLite to support
  transactional updates, relational queries and controlled removal tracking.
- PostgreSQL was deferred because SQLite meets the requirements of the
  local prototype without additional infrastructure.
- Microservices were avoided because independent deployment and distributed
  communication would introduce unnecessary complexity at this stage.
- A chat-first interface was rejected in favour of a searchable directory
  that allows recruiters to browse, filter and compare partners efficiently.
- AI-generated research was deferred until a reliable retrieval, identity
  verification and citation workflow can be established.

## Current coverage and validation

Post-assessment, regular refreshes also include Weil with partial Corporate
coverage across 17 directory filters and Skadden with partial coverage from its
Mergers and Acquisitions partner filter. Partial rosters can add or update
observed partners without inferring removals. The figures below record the
submitted assessment baseline.

The submitted implementation supported seven enabled firms:

- Six firms with verified rosters within their documented scope.
- Gibson Dunn with explicitly labelled partial Corporate coverage.
- Quinn Emanuel is included under its native M&A Litigation practice,
  rather than being presented as a transactional M&A practice.

The assessment snapshot contained 1031 enriched profiles.
Roster coverage and profile enrichment counts are measured separately.

All 35 regression tests passed on 19 November 2026, including tests for
source failures, partial publication, identity normalisation, pagination,
profile enrichment, removal tracking and unexpected partial coverage.

The remaining firms are documented in ASSESSMENT_REVIEW.md. I have not
claimed complete coverage where source access, practice mapping or
pagination could not be reliably verified.

## Final integration testing

On 19 November 2026, I executed the full refresh pipeline and
verified the resulting SQLite database, FastAPI backend and
recruiter interface.

| Metric | Result |
| --- | --- |
| Firms with verified coverage | 6 of 15 |
| Firms with partial coverage | 1 |
| Active roster entries | 1,043 |
| Successfully enriched profiles | 1,031 |
| Profile enrichment coverage | 98.85% |
| Recorded profile enrichment failures | 12 |
| Automated regression tests | 35 passed |

The full refresh returned exit code 3 due to individual profile
enrichment failures. Previously collected roster data remained
available.

Investigation identified six character encoding issues, three
directory-to-profile name variations and three biographies that
could not be extracted.

I corrected the shared HTML decoding implementation to pass raw
response bytes to BeautifulSoup, rather than relying on HTTP
response text decoding.

The correction was validated against a live Milbank profile and
with a new automated regression test. The stored dataset has
not been refreshed again following this correction, so the
reported profile count remains 1,031.

Strict identity validation remains in place to prevent incorrect
profile associations.

Manual frontend testing confirmed:

- Partner search and filtering by firm, office and practice.
- Sorting and pagination.
- Individual partner profile display.
- Saved partners and browser persistence.
- Google research links.
- Recent changes and labelled fictional preview data.
- Verified and partial coverage indicators.

Profile enrichment coverage refers to the collected roster,
not complete coverage of all 15 target firms.

## Production roadmap

### Weekly automated refresh

The existing refresh command is designed to be invoked by a scheduler
without requiring recruiters to run individual connectors.

For an initial deployment, I would evaluate a lightweight scheduled job.
As the workflow grows in complexity, an orchestration service such as
Google Cloud Composer could manage scheduling, dependencies, retries,
execution history and alerts.

The first production improvements would be:

- Per-firm refresh history and visible data freshness.
- Alerts for failed refreshes and unexpected partial coverage.
- Historical roster count checks to detect suspicious reductions.
- Bounded retries and per-domain request limits.
- Protection against overlapping refresh executions.
- Prioritised enrichment of new and stale profiles.

### Scaling from 15 to 50 firms

The source registry and connector interface allow additional firms to
be introduced without rewriting the API or recruiter interface.

I would develop an assisted onboarding workflow that discovers official
directories, identifies common extraction patterns, proposes connector
configuration and validates sample results. Human approval would remain
necessary before enabling a new source.

I would introduce PostgreSQL and server-side search when measured database
contention, data volume or query performance justify that migration.

### Deliberately deferred functionality

- AI-powered recruiter research with source citations.
- Automated cross-firm partner move detection.
- Real addition history beyond the initial verified baseline.
- Shared shortlists, authentication and user management.
- Production cloud infrastructure.
- Canonical office and practice taxonomies across all firms.

These features are valuable but were deferred in favour of establishing a
reliable, source-backed recruitment directory within the assessment scope.

## Assessment documentation

- [DEVELOPMENT_PROCESS.md](DEVELOPMENT_PROCESS.md) explains how I approached the brief, the alternatives I considered, and the evidence that changed my decisions.
- [ASSESSMENT_REVIEW.md](ASSESSMENT_REVIEW.md) maps the implementation to the brief, records coverage and blockers for all 15 firms, and explains what I would change first for weekly operation at production scale.

- [CODEX.md](CODEX.md) provides project-specific technical context, implementation conventions and guidance for continued development.

- [Database guide](database/README.md) explains the SQLite database structure, migrations and responsibilities of the storage layer.

- [Frontend guide](frontend/README.md) explains the recruiter interface, API integration and frontend configuration.


## Run the project locally

### Prerequisites

- Python 3.10 or later
- Git
- Internet access for collecting data from law firm websites
- A modern web browser

The following instructions use Windows PowerShell.

### 0. Clone the repository

```powershell
git clone https://github.com/Rashen97/pinpoint-partners-CTO-test.git
cd pinpoint-partners-CTO-test
```

Alternatively, download the repository as a ZIP file from GitHub,
extract it, and open a terminal in the extracted project directory.

### 1. Set up the environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Populate SQLite

Run the full data collection and profile enrichment pipeline:

```powershell
.\.venv\Scripts\python.exe -m pipeline.refresh
```

The full refresh makes requests to the enabled firms' directories
and individual partner profiles. Execution time depends on network
conditions, source availability and request pacing.

For a quicker functional demonstration, limit profile enrichment
to ten eligible profiles:

```powershell
.\.venv\Scripts\python.exe -m pipeline.refresh --profile-limit 10
```

The limited refresh still processes the enabled firm directories
but restricts the number of individual profiles enriched.

A nonzero exit code may indicate source or profile enrichment
failures. Successfully published data remains available. Review
the refresh output before proceeding.


### 3. Start the API

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
```

Keep this terminal running. The [API docs](http://127.0.0.1:8001/docs) expose the directory and profile endpoints. The API reads SQLite in read-only mode.

### 4. Serve the frontend

Open a second PowerShell terminal at the repository root.

```powershell
.\.venv\Scripts\python.exe -m http.server 8080 --bind 127.0.0.1 --directory frontend
```

Open the [partner directory](http://127.0.0.1:8080/). It connects to the API on port 8001 by default. Search for a partner, open a profile, or try Recent changes.

The coverage indicator shows verified firms and partial coverage separately.
The assessment check found six verified firms and one partial firm, Gibson
Dunn. A subsequent successful refresh can also publish Weil and Skadden as partial.
Wachtell’s browser capture could be parsed, but the live runner received
HTTP 403, so Wachtell is disabled. See the [assessment review](ASSESSMENT_REVIEW.md#coverage-by-firm) for the evidence.

For a standalone preview with fictional records, set the `api-base` meta tag in `frontend/index.html` to an empty string and run only the frontend server. See the [frontend guide](frontend/README.md) for the API contract and configuration details.

## Pipeline checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s pipeline/tests -v
.\.venv\Scripts\python.exe -m pipeline.refresh --directory-only
.\.venv\Scripts\python.exe -m pipeline.refresh --firm paul_weiss
```

Use `--directory-only` to refresh the combined roster without profile enrichment. Use `--firm` to diagnose a single directory connector. By default, targeted runs stop before combined publication and enrichment. See the [SQLite table guide](database/README.md) for what each stage stores.

### Preview Gibson Dunn’s partial coverage

```powershell
.\.venv\Scripts\python.exe -m pipeline.refresh --firm gibson_dunn --publish-partial --profile-limit 3
```

The command collects the configured practice groups and enriches up to three profiles. Refresh
the directory and select the firm to see the saved profiles marked
**Partial coverage**. Remove `--profile-limit 3` to attempt all profiles.
Gibson Dunn also runs in the default refresh under an explicit partial-coverage
setting. It stays outside the verified firm count. A partial import
does not mark absent partners as removed.
