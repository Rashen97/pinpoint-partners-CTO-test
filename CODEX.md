# Pinpoint Partners CTO assessment — Codex handoff

## Start here

This is the handoff for Rashen’s Pinpoint Partners graduate CTO technical assessment. Treat the original assessment PDF as authoritative. The current prototype includes directory extraction, roster normalization and deduplication, and profile enrichment. The refresh pipeline saves each stage as JSON in `mock_database/`. Use `pipeline/firms.yaml` and the connector code to check current configuration. The source probes below record what was observed during discovery.

Suggested first instruction to Codex:

> Read this handoff and the assessment PDF if present. Start with the existing Paul, Weiss connector and run a targeted refresh twice. Check that the mock database roster contains unique partner entries and that overlapping practice labels are retained. Use the source evidence below when expanding firm coverage. Report which firms and practices have verified coverage and which are pending.

## Assessment brief

- Build a useful, current view of **every partner in the Corporate and M&A practices of 15 named law firms, across all offices**. Include partners in either relevant practice, deduplicate overlaps, and keep the firm's native labels. Exclude associates, counsel, and retired partners. Document ambiguous practice labels rather than relying on keyword matches.
- Pinpoint Partners is the recruiter. The law firms are the employers being tracked, not necessarily clients. The product is for recruiters preparing to call partners or mapping the market. Useful questions include who the person is, which office and firm list them, what work they do, and what has changed. Previous firms are useful only when supported by a source.
- The assessment is time-boxed to **about six hours**. Deadline in the brief is **5 pm UK time on Thursday 19 November 2026**. It explicitly values judgement, appropriate scope, handling changing websites, weekly operation, and a credible path from 15 to 50 firms.
- Submit a runnable public repo or one shared with `sp@pinpoint-careers.com`, plus an honest time-spent figure. There is no follow-up interview after the task, but written questions are possible. README should cover setup, who it is for and why, architecture and tradeoffs, alternatives rejected, deliberate omissions, growth and what changes first, and stack choice. AI is permitted, not required. Rashen must be able to explain all submitted code. Treat sites and people's public professional data as in a real system.
- Prior interview context: interviewer Stefan Pillinger. Pinpoint discussed Microdec, scattered emails, duplicate records and manual entry. Those problems informed overall product thinking, but replacing the CRM is **not** this assessment.

## Agreed product and implementation direction

1. **Directory first.** Search by name and filter by firm, office, and practice. Open a profile to scan source-backed facts and bios. Show a source link and freshness date. A small weekly changes view is more valuable than a polished dashboard.
2. **Manual refresh first.** `refresh.py` is the CLI entry point. Run `python -m pipeline.refresh` from the repository root for all refresh-enabled firms, or add `--firm paul_weiss` for a targeted run. No deployed scheduler needed for the prototype, but document how the same command can be run weekly.
3. **Adapters, not 15 separate programs.** `firms.yaml` says where to look and stores confirmed settings. Adapter code decides how to make and parse the request. Share code when the source shapes really match. Every adapter returns the same partner fields, and a common refresh path validates, saves, and compares them. Point the parser at the response body, not at the browser's rendered page unless using browser automation intentionally.
4. **Local JSON mock database.** The pipeline saves connector diagnostics, verified rosters, and profile enrichment under `mock_database/`. The combination of `firm_key` and canonical `profile_url` identifies a roster entry and determines its `partner_entry_id`. Merge labels across overlapping searches. Keep identity scoped to each firm's roster entry.
5. **Separate roster ingestion from bio enrichment.** The roster source proves membership and gives profile links. Fetch bio pages for details beyond what the roster provides. Refresh the roster weekly, update bios on a separate cadence, and regenerate AI briefs only if the source changes. Keep source URLs and checked dates.
6. **Failure must not look like a departure.** Validate each firm independently. A blocked, partial, empty-looking, or anomalously small run must not overwrite the last good roster. Save per-firm status and timestamps. Compare only validated complete rosters. Say “newly listed” or “no longer listed,” not “joined” or “left,” unless confirmed by a credible source. The first snapshot has no historical changes. Not-yet-implemented firms and unverified coverage must be visible.
7. **Optional AI second.** The preferred UI is a searchable directory with a side panel, “Ask about this partner.” Start with the saved profile and give sourced answers. Optionally add Gemini with Google Search grounding for a question the profile cannot answer. Keep the answer separate from the roster, cite source/date, and say when evidence is missing. Suggested call openers must be presented as suggestions. AI could normalize ambiguous practice labels with supporting evidence, but deterministic fields do not need it. No MCP server, agentic crawler, vector store, or Vertex/Agent Search index for the MVP. If using Gemini/Vertex AI, make it optional so the reviewers can run directory and refresh locally without GCP credentials. FastAPI is a candidate for the later service/UI, not necessary for the first scraper.

### Local setup and first acceptance check

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Work from the project root. Keep `.venv/`, secrets, and generated JSON snapshots out of Git. Run `python -m unittest discover -s pipeline/tests -v` for the test suite. For a live smoke test, run `python -m pipeline.refresh --firm paul_weiss` and inspect `mock_database/partner_entries/paul_weiss.json`. Use `python -m pipeline.refresh --profile-limit 10` to refresh the combined roster and exercise profile enrichment on up to ten entries.

## What the captured requests mean

A DevTools Request URL is just one part of the actual request. GET query strings and POST query strings go in `params=`. HTML form bodies go in `data=`. JSON request bodies go in `json=`. POST does not imply a separate body. Check Headers, Payload, and Response on the same network entry. Reproduce the public directory's own filters and pagination, and don't commit captured credentials, browser cookies, or per-request identifiers. A public directory returning 403 to a plain Python fetch is a failed source test, not proof the directory is empty. If a publicly accessible page requires JS, browser automation is an option when permitted and practical, but establish role and practice filters plus the end of pagination.

## Firm-by-firm source evidence

All probes were performed or captured during this chat on 18 Nov 2026. Counts are observations, not constants. “Captured” means request/response observed in the user's browser. “Tested” means a direct request returned data in our checks. Neither automatically establishes full coverage.

### Paul, Weiss, Rifkind, Wharton & Garrison — best first adapter

- Directory: https://www.paulweiss.com/professionals
- **Tested GET returning HTML:** https://www.paulweiss.com/umbraco/surface/lawyerssearch/GetLawyersResult
- Query params: `pageId=1492`, `pageSize=12`, `pagingNumber=1`, `position=Partner`, `industries=All`, `offices=All`, `schools=All`, `lastname=All`, `searchText=All`. Set `practices` to `Corporate` or `Mergers and Acquisitions` in separate requests. The website label uses “&” for M&A, but the filter value spells out “and.”
- Tested Corporate page 1 and M&A pages 1 and 2. They returned HTTP 200, 12 partner profile links per page, and no overlap between the two M&A pages. Observed last-page markers were 17 for Corporate and 10 for M&A. Read the pager from the HTML (`data-page`), don't hardcode the page count. Merge overlapping practice memberships.
- Profile href prefix: `/professionals/partners-and-counsel/`. Use the returned href, deduplicate repeated links within a card, and check actual title (the URL path includes counsel). The attached response is unfiltered, useful for parser structure and exact option `data-val` values. Recognize `p.position` as the role in that capture.

### Sullivan & Cromwell — tested JSON GET

- Directory: https://www.sullcrom.com/LawyerListing
- Official M&A directory link: https://www.sullcrom.com/LawyerListing?custom_is_practices=69620
- **Tested GET:** https://searchg2.crownpeak.net/sullivancromwell-sullcrom-live/select/
- Query test: `q=*:*&wt=json&fl=title&rows=3` plus three separate `fq` params: `custom_s_type:Lawyer`, `custom_is_practices:69620` (M&A), `custom_i_type:25257` (Partner). Use a list of key-value tuples in Python so repeated `fq` keys don't overwrite each other. Returned HTTP 200, `response.numFound = 94`, and partner names in `response.docs`.
- The site's script uses `start` and `rows`, but a full paged scrape was not tested. The test requested `fl=title` only. Inspect public fields for the profile path, office and labels before finalizing. Any separate Corporate filter remains unverified.

### Kirkland & Ellis — captured JSON GET pattern

- Directory: https://www.kirkland.com/lawyers
- Endpoint: https://www.kirkland.com/api/sitecore/ProfessionalsApi/Lawyers
- DevTools showed requests such as `?letter=A` and `?letter=B`. JSON rows have `Name`, `Position`, `Offices` (list), and relative `Url`. `Description` was null in a sample. Confirm exact role/practice query, letters versus pagination, and whether an all-surnames request works. The unfiltered letter examples are not enough to claim full roster coverage.
- Directory HTML has a JavaScript results template, not static roster rows. Individual profiles, e.g. https://www.kirkland.com/lawyers/a/abate-anthony, have readable HTML with `.profile-heading__name`, `.profile-heading__position`, office links and an Overview section. Anthony Abate is an **Associate**, a negative test case, not an in-scope partner.

### Wachtell, Lipton, Rosen & Katz — captured HTML GET

- Results and directory share https://www.wlrk.com/attorneys/
- User's browser returned HTTP 200 for `?asf_l=View%20All`. The pasted source contained 286 distinct `/attorney/` profile links and form options for `asf_pa=corporate`, `asf_p=partner`, `asf_l=View All`.
- No general M&A option was present in the practice dropdown. There was a separate Real Estate M&A option, not equivalent to general M&A. Corporate is the starting rule, document it.
- Direct Python test for the combined Corporate + Partner + View All request returned 403 from this environment. Browser confirmation of the filtered result and testing the eventual runner are still needed. Do not claim the 286 are in scope.

### Quinn Emanuel Urquhart & Sullivan — captured POST, HTML response

- Directory: https://www.quinnemanuel.com/attorneys
- Endpoint: https://www.quinnemanuel.com/Umbraco/surface/AttorneysListSurface/GetAttorneyListByFilter
- Captured URL query: `byCountry=1757&byChar=a&byProfileType=&bySearch=&byOffice=&byPracticeArea=&byLawClerk=&byAdp=`. Method POST. Filters shown here are query params. Check whether DevTools shows a separate body. Country value meaning/all offices, role/practice IDs and later batches are unverified.
- HTML list uses `.attorney-card`, `h3 a` for name and profile href, `.designation` for title, `.location a` for office(s).
- The firm describes itself as litigation-only. Its relevant published labels include **Mergers & Acquisitions Litigation** and **Corporate Governance Litigation**. It is explicitly in the list, so propose including those as separately labelled adjacent practices, not as transactional M&A. Document the choice and don't implicitly apply the same broadened rule to every firm. Official source: https://www.quinnemanuel.com/practice-areas/mergers-acquisitions-litigation/

### Davis Polk & Wardwell — captured Algolia JSON POST

- Directory reference: https://www.davispolk.com/lawyers
- Search URL: `https://dbc8kua830-dsn.algolia.net/1/indexes/*/queries`. Method POST. Index `lawyer_search_en`. Filters and page are in the JSON request body. The captured body contained a `requests` array with `facetFilters: [["job_title:Partner"]]` on the result query.
- First response `results[0]` showed 211 hits, 11 pages, `page=0`, `hitsPerPage=20` for the Partner-only search, not the Corporate/M&A roster. Read `hits` for results. The second response had 0 hits per page and is not the roster. Hits have `name`, `job_title`, `office`, `practice` (list), `practice_display`, and relative `url`.
- The frontend request included an apparently time-limited search credential and per-request ID. Neither belongs in static YAML or the repo, and no credential is included here. Capture practice and pagination from the public UI or prefer a viable public source. Check the official M&A Team page as an alternative and verify whether its listing is complete: https://www.davispolk.com/mergers-acquisitions

### Simpson Thacher & Bartlett — captured form POST, JSON response

- Directory: https://www.stblaw.com/our-team
- M&A team tab: https://www.stblaw.com/client-services/practices/corporate/mergers-and-acquisitions?contentId=2
- Endpoint: https://www.stblaw.com/dataservices/DataServices.Content.Services.Json.AttorneyLookup/TeamMembers
- Method POST, URL-encoded form body. Captured `position=b4e5c90e-743d-6a02-aaf8-ff0000765f2c`, `take=8`, `skip=0`, `page=1`, `pageSize=8`, `searchCount=1`. Other fields captured as blank: `clientSolutions`, `industries`, `practice`, `offices`, `law[]`, `lawSchoolName`, `school[]`, `schoolName`, `selectedLetter`, `pageFilter`, `pageFilterId`, `roleId`. A `searchId` appeared in both request and response, but its necessity/lifecycle is unverified. Do not hardcode the captured ID.
- Response uses `TeamModels` and `total`. Captured 8 rows with `Role: Partner`, reported 490 total for the position-filtered request with practice blank. Check the row's actual role because the UI can group Partners and Counsel. Fields include `FullName`, `Role`, `Titles`, `Office`, `PracticeFocuses[].Text`, `UrlName`. Bios can be blank in this response.
- For partners, verified profile URL pattern: `https://www.stblaw.com/our-team/partners/{UrlName}`. Use `UrlName` verbatim. Tested `j-alden-millard`, `meredith-j-abrams`, and `adam-s--aderton` (double hyphen).
- Still needed: capture Corporate and M&A practice IDs and page 2 to verify how `skip` and `page` change. A fallback of filtering the full roster locally by exact labels is only safe after confirming full coverage and label completeness.

### Remaining sources to finish

| Firm | Official starting point | Evidence and next step |
|---|---|---|
| Gibson, Dunn & Crutcher | https://www.gibsondunn.com/people/?_people_practices=mergers-and-acquisitions | Direct GET returned 20 profile links. `&_paged=2` returned the same 20. Page has WP Grid Builder `Load more` and endpoint templates at `/?wpgb-ajax=action` and `/wp-json/wpgb/v2/filter/?action=action`. Exact live request not verified. Initial HTML also contained a broad total, so confirm the practice facet really determines roster membership. |
| Latham & Watkins | https://www.lw.com/en/people | Direct GET returned 200, no profile anchors found. Public source configures Coveo under `/coveo/rest`, but actual lawyer request/body is unverified. Capture after selecting the relevant practice. |
| Cravath, Swaine & Moore | https://www.cravath.com/people/index.html | Indexed view shows a Partner section with Corporate labels and View All. Direct fetch got 403 in test environment. Capture View All and the practice filter in a normal browser. |
| Milbank | https://www.milbank.com/en/professionals/index.html | Directory has Corporate and Mergers and Acquisitions filters. Direct fetch returned 403. Capture the browser requests for those filters, don't infer numeric IDs from unrelated URLs. |
| Paul Hastings | https://www.paulhastings.com/professionals?facets=ph_nested_practice_areas%3DMergers%2B%2526%2BAcquisitions | Known M&A-filtered link. Raw GET returned 200 but no profile anchors were found. Capture practice, title, and next-page requests. |
| Skadden, Arps, Slate, Meagher & Flom | https://www.skadden.com/professionals?hasSearched=true&practice=8551cacf-412c-4b5f-bfb4-000000037583 | Official M&A-filtered URL and View More. Raw GET returned 403 in test environment. Capture Position and View More. The practice filter can include partners with a different primary title, so retain practice labels. |
| King & Spalding | https://www.kslaw.com/people | Its official M&A View All link is `https://www.kslaw.com/search?filter_capability=Mergers+%26+Acquisitions+%28M%26A%29&section=people`. A static view showed a zero-result shell, while the practice page names partners. Raw GET of the filtered link returned 403. Actual results request not captured. |
| Weil, Gotshal & Manges | https://www.weil.com/people | Use Practice / Capability and role filters. The M&A practice page's Key Contacts is not the full roster. Raw GET returned 403. Actual results request not captured. |

## Source samples to bring into Codex if available

Put the PDF and any useful local HTML/JSON fixtures in the project or point Codex at them. The names below are those used in this chat. Do not add full raw public-profile responses, sessions, contact fields or credentials to a public repo by default. Use small sanitized fixtures for parser tests.

- `Pinpoint_Partners_CTO_Technical_Assessment.pdf` — original brief.
- `Pasted text(20261118-195355).txt` and `Pasted text(20261118-195458).txt` — Kirkland profile source and directory source, respectively.
- `Pasted text(20261118-202054).txt` — Quinn Emanuel HTML cards.
- `Pasted text(20261118-203145).txt` — Davis Polk Algolia JSON response.
- `Pasted text(20261118-210756).txt` — Paul, Weiss HTML results and filter controls.
- `Pasted text(20261118-211137).txt` — Wachtell View All HTML.
- `Pasted text(20261118-211428).txt` — Simpson Thacher JSON response.

## Verify before calling it done

Check first-run setup in a fresh environment. Test parsers for both HTML and JSON, pagination with distinct batches, deduplication across Corporate/M&A, and a failed or partial refresh that leaves the prior roster untouched. Show a per-firm coverage/status table. If you run out of time, report exactly which firms and practices are confirmed or missing. A research note or captured endpoint alone is not a delivered roster.
