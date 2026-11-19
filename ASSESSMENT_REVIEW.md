# Assessment review

The target is every Corporate and M&A partner across all offices at the 15 firms named in the brief. This ledger records what I could verify during the assessment. It reflects the source review and local runs as of 19 November 2026. [Source configuration](pipeline/firms.yaml)

## Assessment criteria

I used these criteria to decide what the prototype needed to demonstrate and what I would validate before relying on it in production.

| Criterion | What works today | What I would improve for regular use |
| --- | --- | --- |
| **Recruiter value** | Recruiters can find a partner, save a shortlist, read a firm-sourced profile, and open a focused web search. Recent changes shows when a partner is no longer listed and includes labelled fictional examples. | Show when a partner is first seen after a firm’s initial verified list. Report a move between firms when there is supporting evidence, such as a hiring announcement. |
| **Coverage and data quality** | Six firms have verified rosters. Gibson Dunn has partial coverage across M&A and four Corporate practices. The table below explains the status of all 15 firms. The system tracks verified partner lists separately from collected profiles. | For each new firm, check that the source covers the relevant partners, practices, offices, and pages. Show when each firm was last checked and investigate unexpected drops before publishing an update. |
| **Engineering quality** | The project collects, checks, and saves data before displaying it. The directory can read the saved records, and the refresh process controls changes to them. | Keep a history of each firm’s updates so the team can trace a change back to its source. Test what happens when a site changes, returns incomplete results, or becomes unavailable. |
| **Weekly operation and scale** | One command refreshes firm directories and collects profile details. It is designed to run as a scheduled job. If one firm fails, the others can update while the failed firm keeps its last verified list. | Run the command weekly using a tool such as Google Cloud Composer. Add alerts and show when each firm was last verified. For 50 firms and beyond, build a tool that takes firm names and optional homepages, finds candidate directories, and checks sample results. A reviewer would confirm coverage before enabling each source. [Google Cloud scheduling guide](https://docs.cloud.google.com/composer/docs/composer-3/schedule-and-trigger-dags) |
| **Prioritisation and scope** | I focused on getting firm data onto the recruiter’s screen and documenting the coverage gaps. I deferred AI chat, shared shortlists, and automated move detection. | Make weekly updates reliable and show how current the data is. Use recruiter feedback to decide whether broader coverage or better market-change tracking should come next. |
| **Responsible collection** | The project records where professional profile details came from and when they were checked. The refresh visits firm directories one at a time and only publishes results that pass its coverage checks. | Check each site’s access rules, identify and pace requests, and stop when access is persistently blocked. Decide which fields to keep, for how long, and how to correct records. |
| **Communication and reproducibility** | The README explains how to run the project and recognise sample data. The development log explains the decisions, and this review records the coverage evidence and gaps. | Document how to add a firm, handle a failed update, and check whether a list is current. Include the actual time spent in the assessment submission. [README](README.md) · [Development process](DEVELOPMENT_PROCESS.md) |

## Coverage by firm

| Firm | Status | Evidence and remaining work |
| --- | --- | --- |
| Kirkland & Ellis | Direct access blocked | The official directory has Practice, Level, and Office filters in web review. A direct directory request returned HTTP 403. The captured results endpoint previously returned HTTP 500. [Directory](https://www.kirkland.com/lawyers) |
| Wachtell, Lipton, Rosen & Katz | Automatic refresh disabled | The connector read the Position column and extracted 34 Corporate partners from 122 attorney rows saved in a browser capture. The same Corporate request returned HTTP 403 (Forbidden) from the Python runner. The capture verifies the parser. Automatic publication requires a source the runner can access and verify on every run. [Directory](https://www.wlrk.com/attorneys/) |
| Quinn Emanuel Urquhart & Sullivan | Enabled for M&A Litigation | The practice team's View More endpoint returned 62 attorney cards, including 60 partners and a chair counted among those partners, with no further pages. A linked profile passed enrichment. This roster covers the firm's published M&A Litigation team. The firm describes itself as litigation-only and says it has no corporate transactional practice. [Directory](https://www.quinnemanuel.com/attorneys) · [M&A Litigation](https://www.quinnemanuel.com/practice-areas/mergers-acquisitions-litigation/) |
| Davis Polk & Wardwell | Enabled, roster verified | Collected 190 unique partners across all 22 published Corporate practice groups, including M&A, with all offices selected. Environmental’s complete team listed counsel and associates only. The connector checks listed titles because the site’s Partner filter can also return counsel. [M&A team](https://www.davispolk.com/mergers-acquisitions/team) · [Corporate practices](https://www.davispolk.com/corporate) |
| Simpson Thacher & Bartlett | Replacement source found, full run rate limited | The new public listing API reported 421 Corporate and 153 M&A partners before deduplication. The replacement connector verified the first 20 Corporate pages, then received HTTP 429. A paced retry and a profile request were also rate limited, so the firm remains disabled pending complete verification. [Directory](https://www.stblaw.com/our-team/) |
| Paul, Weiss, Rifkind, Wharton & Garrison | Enabled | The combined refresh stored 216 active entries across Corporate and M&A. At the time of the check, 214 active profiles had saved enrichment. [Directory](https://www.paulweiss.com/professionals) |
| Gibson, Dunn & Crutcher | Enabled with partial scope | The connector retrieved 278 unique partners across M&A, Capital Markets, Private Equity, Finance, and Investment Funds, without an office filter. Each search was checked against the reported total. The firm’s London training materials support the selected Corporate practices, and global Corporate scope remains unverified. [Directory](https://www.gibsondunn.com/people/) · [Firm training materials](https://www.gibsondunn.com/wp-content/uploads/2025/08/LE-Recruiting-TrainingWithGDCLondon-0825-v4.pdf) |
| Latham & Watkins | Directory found | The firm has official People and M&A pages. Verify how search combines Partner, practice, and office filters, and how it pages through the results. [Directory](https://www.lw.com/en/people) · [M&A practice](https://www.lw.com/en/practices/mergers-and-acquisitions) |
| Cravath, Swaine & Moore | Enabled | The Corporate and M&A searches matched their reported totals. The combined refresh stored 65 unique active entries. A limited test enriched three profiles and the API returned all three. [Directory](https://www.cravath.com/people/index.html) |
| Milbank | Enabled | The scope includes the firm's Corporate and M&A filters, Distressed M&A, and explicit regional equivalents. The connector checks pagination without an office restriction and retains Partner results. Mixed and adjacent labels do not qualify on their own. [Directory](https://www.milbank.com/en/professionals/index.html) |
| Sullivan & Cromwell | Enabled | The firm calls its Corporate group General Practice. The connector uses that filter plus M&A and Financial Services M&A. Sorting by source record ID prevents overlap across pages. [Directory](https://www.sullcrom.com/LawyerListing) · [Corporate group](https://www.sullcrom.com/careers/your-career-at-sc) |
| Paul Hastings | Directory found | The directory showed a loading shell in web review. An M&A facet is known. The results feed, broader Corporate mapping, Partner filter, and pagination remain unverified. [Directory](https://www.paulhastings.com/professionals) |
| Skadden, Arps, Slate, Meagher & Flom | Directory found | The directory exposes Practice, Location, Position, and View More controls. The initial response contains a result template. Verify rendered partner results and the entire page sequence. [Directory](https://www.skadden.com/Professionals) |
| King & Spalding | Directory found | The official M&A capability links to a people search. The Corporate mapping and all-office Partner results remain unverified. [Directory](https://www.kslaw.com/people) · [M&A capability](https://www.kslaw.com/capabilities/mergers-acquisitions-m-a) |
| Weil, Gotshal & Manges | Directory found | The directory exposes M&A, Partner, and Office filters. Cross-check the Corporate department against the directory filters and verify full pagination. [Directory](https://www.weil.com/people) · [Corporate department](https://www.weil.com/experience/departments/corporate) |

## How coverage affects the product

The default refresh enables Paul Weiss, Cravath, Quinn Emanuel, Milbank, Sullivan & Cromwell, Davis Polk, and Gibson Dunn. The directory reports **6 of 15 firms verified** and **1 with partial coverage**. Gibson Dunn’s configured practice refresh can add or update observed entries. Full Corporate coverage still needs verification before it can count as verified or produce removals.


A failed or incomplete extraction preserves the previously published
roster. Explicitly approved partial coverage can publish valid observations
without inferring removals or overwriting verified roster entries.

The refresh distinguishes expected partial coverage from unexpected
deterioration. Unexpected partial coverage returns a nonzero exit code
while preserving existing data and publishing eligible observations.
This allows a future scheduler to detect operational problems without
discarding useful information.

All 35 regression tests passed, including a dedicated test for unexpected
partial coverage and preservation of previously verified partners.

A remaining production limitation is that a source could return an
apparently complete but unusually small roster. Historical count
comparisons and investigation thresholds would provide additional
protection against false removal notifications.


## Ideas and future improvements

- **Automate firm discovery and scraper setup.** I would build an AI-assisted tool that takes a list of firm names and optional homepages. It would find official directories and practice pages, identify how the site lists profiles, and propose settings for a shared scraper or draft a connector where needed. A trial run would show which roles, practices, offices, and pages it captured. A reviewer would approve the source before it enters the regular refresh. I would test this first on a firm with a verified list and a firm we don’t yet cover, then compare completeness and manual effort.
- **Schedule and monitor weekly updates.** I would use an orchestration tool such as Google Cloud Composer to run the existing refresh command on a schedule. Each run would record which firms succeeded, flag unexpected drops in results, and alert an operator when a source needs attention. I would prevent overlapping runs, show the last verified date for each firm in the directory, and prioritise collecting details for new or stale profiles. [Google Cloud scheduling guide](https://docs.cloud.google.com/composer/docs/composer-3/schedule-and-trigger-dags)
- **Replace the Google link with an AI research assistant.** I would add a retrieval-augmented generation (RAG) assistant alongside the directory. A recruiter could ask, for example, what deals a partner has advised on recently. The assistant would use the saved profile for context, search the web when the question goes beyond it, and summarise the results as part of the conversation. Answers would link to their sources, show dates where available, and explain when the evidence is incomplete or the person’s identity is unclear.
- **Track moves between firms and support lateral-hire research.** I would record additions and removals after each firm’s first verified list, then use those observations to flag possible moves. A recruiter could review the source links and dates. A destination firm’s announcement or other corroborating evidence would support marking a move as confirmed. The system would record when it observed the change and the effective date when a source provides one.

## Time log

The Git timeline covers approximately **5 hours and 6 minutes**, from the initial commit on 18 November to the documentation milestone on 19 November 2026. I spent the interval between the initial commit and the first project structure planning my approach and organising the work. That time is included in the estimate. The figures come from commit timestamps, so they give an approximate work window rather than a stopwatch total.

| Date | UK time | Milestone | Commit |
| --- | --- | --- | --- |
| 18 November | 21:44 | Initial repository commit | `68fa73e` |
| 18 November | 23:50 | Planning and organisation, followed by the initial project structure | `07642f1` |
| 19 November | 00:59 | Refresh pipeline and JSON prototype | `032ce16` |
| 19 November | 01:04 | SQLite storage | `6164393` |
| 19 November | 01:28 | Partner directory and live research interface | `e5e6d28` |
| 19 November | 01:52 | SQLite-backed API and frontend integration | `08789df` |
| 19 November | 02:26 | Expanded firm coverage and Recent changes preview | `d8c7567` |
| 19 November | 02:50 | README, development log, and assessment review | `817ea8a` |


## Time log

Total estimated active working time: approximately 7 hours.

I worked on the assessment across two sessions, beginning on the evening
of 18 November and continuing on the morning of 19 November 2026.

The initial Git timeline spans approximately 5 hours and 6 minutes.
This included planning, implementation, documentation and a short
break following the initial repository commit.

I resumed work the following morning to improve firm coverage,
introduce partial-scope publication, review refresh failure handling,
and complete additional regression testing.

The total is an honest estimate of active working time, excluding
breaks and overnight downtime.

I exceeded the suggested six-hour time budget by approximately one
hour, focusing the additional time on data integrity, reliable refresh
behaviour and verification rather than introducing further product
features.


## How I used AI

- **Brainstorming the recruiter workflow.** I used AI to explore how recruiters prepare for calls and track market changes. I settled on a searchable directory with source-backed profiles and live research.
- **Exploring and building the pipeline.** I used AI to work through scraping options and identify what I needed from each site, including the directory URL, request method, role and practice filters, and a way to check whether all results had been retrieved. I built scraping scripts and used AI to help implement additional connectors. I checked the outputs against live responses, reported totals where available, and profile enrichment runs.
- **Evaluating design tradeoffs.** I used AI to challenge design choices and identify limitations. When Simpson Thacher’s endpoint failed, I examined how waiting for every firm held back valid results. I changed the refresh policy so verified firms can update and a failed firm keeps its last verified data. A regression test checks that behaviour.
- **Building the interface and API scaffold.** Once I had settled the frontend concept, I used AI to build the frontend and scaffold the FastAPI application. That helped me spend more of the assessment on the collection pipeline, data quality, and backend integration.
- **Refining the documentation.** I used AI to organise the README, development log, and assessment review and improve their clarity and grammar.
