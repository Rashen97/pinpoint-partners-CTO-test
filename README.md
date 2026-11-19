# Pinpoint partner directory

Pinpoint’s recruiters need to prepare for calls with individual partners and keep up with changes across law firms. This project gives them a searchable directory of Corporate and M&A partners, with filters for firm, office, and practice. Recruiters can save a shortlist in their browser, read a source-backed profile, and open an editable Google search for recent deals, press coverage, or firm announcements.

The directory is the starting point because recruiters can scan a market segment and open a profile in the same workflow. Recent changes shows recorded removals and includes a labelled fictional preview of additions and removals. The prototype leaves AI chat, shared shortlists, and cross-firm move detection for later.

The pipeline uses Python connectors to collect and validate firm rosters, then enriches the partner profiles. SQLite keeps both stages in a single local database. FastAPI exposes the enriched directory and profile details through a typed API, and the browser interface runs without a frontend build step.

## Assessment documentation

- [DEVELOPMENT_PROCESS.md](DEVELOPMENT_PROCESS.md) explains how I approached the brief, the alternatives I considered, and the evidence that changed my decisions.
- [ASSESSMENT_REVIEW.md](ASSESSMENT_REVIEW.md) maps the implementation to the brief, records coverage and blockers for all 15 firms, and explains what I would change first for weekly operation at production scale.

## Run the project locally

Use Python 3.10 or later. Run these commands from the repository root in PowerShell.

### 1. Set up the environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Populate SQLite

```powershell
.\.venv\Scripts\python.exe -m pipeline.refresh
```

The refresh needs network access to the enabled firms’ sites. It creates `database/partners.db`, applies migrations, and updates the combined roster for firms that pass validation. It retains the last verified entries for firms that fail or return partial results. Those issues appear in the run summary and cause a nonzero exit code even when other firms update successfully. Profiles appear in the directory after enrichment is saved.

For a quicker run from a clean checkout, use `--profile-limit 10`. This runs every enabled firm’s directory refresh and attempts up to ten profiles **across the firms verified in that run**.

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

For a standalone preview with fictional records, set the `api-base` meta tag in `frontend/index.html` to an empty string and run only the frontend server. See the [frontend guide](frontend/README.md) for the API contract and configuration details.

## Pipeline checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s pipeline/tests -v
.\.venv\Scripts\python.exe -m pipeline.refresh --directory-only
.\.venv\Scripts\python.exe -m pipeline.refresh --firm paul_weiss
```

Use `--directory-only` to refresh the combined roster without profile enrichment. Use `--firm` to diagnose a single directory connector. Targeted runs stop before combined publication and enrichment. See the [SQLite table guide](database/README.md) for what each stage stores.
