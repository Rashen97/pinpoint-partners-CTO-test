# Development process

I started with two recruiting tasks from the brief: preparing for a call with a particular partner and keeping up with changes across firms. The six-hour target made prioritisation part of the exercise. I used ChatGPT to brainstorm and help write parts of the code, then checked the resulting behaviour against source responses, local tests, and runs through the pipeline.

## 1. Start with the recruiter workflow

I considered a chat-first interface. A recruiter often needs to scan many partners, narrow a market segment, and return to a shortlist. A searchable directory makes those tasks repeatable without requiring a series of prompts. I added filters for firm, office, and practice, plus a profile drawer that keeps the results in context. Saved partners use browser storage so the prototype can offer a shortlist without introducing accounts or shared persistence.

For call preparation, I wanted a recruiter to reach current deal and press coverage from a profile. I chose an editable Google query prefilled with name and firm, with shortcuts for deals, press, and firm announcements. The recruiter chooses when to send the query. I deferred AI chat until there is a retrieval and citation workflow that can handle ambiguous names and missing evidence. The browser’s search results stay outside the stored firm-sourced profile.

I added Recent changes because weekly market movement is a separate recruiting task. The connected API supplies recorded removals. A clearly labelled fictional preview demonstrates additions and removals while the real history is empty or only contains removals.

## 2. Separate roster extraction from profile enrichment

I started by inspecting the firms’ public directories, practice pages, and the requests made by their search interfaces. Some expose HTML cards, some return JSON, and some wrap rendered cards in JSON. I recorded source URLs, filter settings, and coverage findings in `pipeline/firms.yaml`. A directory URL proves where to start. The evidence for a usable roster also needs the right role, practice scope, offices, and every result page.

Firm-specific extractors produce a common `PartnerEntryInfo` record with the name, role, native practice labels, offices, and profile URL. Directory data answers who was listed. Profile enrichment follows those URLs and adds biography and any available professional fields to `PartnerProfileInfo`, with a check timestamp and a content hash. A failed biography request leaves roster membership intact.

I kept `python -m pipeline.refresh` as the operational entry point. It runs enabled directory connectors sequentially, validates their output, writes the combined entries, and then enriches that dataset. Sequential extraction simplified debugging and made request load easier to reason about. Profile fetching and parsing live in a separate package. One shared HTML parser uses per-firm selectors, keeping routine markup differences in configuration. A site with a different profile format can justify a custom parser later.

The full run exercises the workflow a scheduler will eventually invoke. A targeted `--firm` run diagnoses a single directory source and stops before combined publication or enrichment. `--directory-only` checks combined extraction and storage, and `--profile-limit` caps enrichment across the firms verified in that run.

## 3. Keep publication and identity tied to evidence

I began with local JSON files so I could inspect raw and normalised data while the schema was changing. The JSON design distinguished diagnostic output from a verified roster and used atomic file replacement. I then moved to SQLite to support versioned migrations, transactional writes, and backend queries on the same machine. SQLite kept setup small for the assessment. The pipeline owns writes and migrations, and the API opens the file read-only.

The raw per-firm tables retain extraction output and diagnostics. The verified per-firm tables preserve successful work. I initially updated `partner_entries_all` only when every enabled firm passed the refresh checks. I changed that after one broken source held back healthy firms. The combined table now updates for the firms verified in that run, and preserves the previous entries for the others. Enrichment writes to `partner_profiles_all` for the verified firms. The command still returns a nonzero exit code when a source fails or returns partial data, so an operator can act on the failure.

A deterministic `partner_entry_id` is derived from the firm and canonical profile URL. This makes repeat loads predictable and avoids merging people by name. A new firm or changed profile URL can produce a new entry ID. Stable aliases would be needed to carry identity across a URL change, and cross-firm matches require a separate person identity supported by evidence.

Profile writes use the entry ID and a content hash to update changed profiles, skip unchanged results, and guard against overwriting newer stored content with older observations. Limited or partial enrichment retains previously saved profiles for current entries. A complete, verified combined refresh can set `no_longer_listed_at` when an entry is absent. Reappearance clears that timestamp. A source error, partial scrape, or failed profile fetch provides insufficient evidence to change listing status.

For the next version of Recent changes, I would record first sightings after a firm’s baseline snapshot so onboarding a source does not create a wave of apparent hires. An addition and removal could suggest a move for review. A confirmed move would need stronger evidence, such as an announcement naming both firms. Listing observation dates should remain distinct from effective dates.

## 4. Let the interface shape the API

I started with the two reads the UI needed. `GET /api/partners` returns the browsable directory and available coverage and change information. `GET /api/partners/{partner_entry_id}` loads the profile when a recruiter opens the drawer. FastAPI gave me typed response models and an OpenAPI page for checking the contract. I separated routes, schemas, and queries and kept the frontend build-free. The labelled standalone preview lets the interface be reviewed when a live source is unavailable.

The first SQLite integration returned directory entries even when they had no enrichment. I revised it so both reads start from `partner_profiles_all`. The entries table remains the enrichment input and supplies identity, source links, and current listing status through the join. The directory uses profile role, office, and practice values where available, with roster values as a fallback. This means a recruiter can open a profile as soon as it appears in the directory. It also means that verified firm coverage and the number of browsable profiles can diverge during enrichment. The UI has a specific empty state for a database with no enriched profiles. Directory records, coverage, and changes are read from one SQLite snapshot.

## 5. Use source failures and scope differences to test the design

When the connected UI first showed zero partners, I checked the API and SQLite separately. The request succeeded and the Paul Weiss firm table held 216 entries. The combined tables were empty because Simpson Thacher’s legacy endpoint returned HTTP 404 and held back publication. I isolated the full path by enabling only Paul Weiss and using the default refresh. That exercised the combined entries and profile stages that a targeted run skips. The failure made the cost of the combined publication gate concrete.

I used each firm’s own terminology and checked how the source establishes completeness:

- **Cravath.** Its main directory initially shows a preview. The public partner search returns Corporate and M&A results with totals to check. The connector uses structured position data because some partner rows omit the headline title.
- **Milbank.** The search returns paginated attorney cards. I checked offsets, declared totals, and duplicates before accepting the results. I included the native Corporate and M&A filters, Distressed M&A, and explicit regional equivalents. A mixed practice label alone is insufficient to assign in-scope work to everyone it returns.
- **Quinn Emanuel.** I initially read the brief as transactional and treated the firm as a scope exception. Because the brief explicitly lists the firm, I included its published M&A Litigation team under the native label. The practice team’s expansion endpoint supplied the roster. The general directory capture showed multiple roles and did not establish practice scope.
- **Sullivan & Cromwell.** I initially found M&A but missed the broader Corporate group, which the firm calls General Practice. I verified that mapping against the firm’s description and added both explicit M&A filters. The first multi-page Corporate extraction repeated a profile. Sorting by source record ID gave stable page boundaries in the live check.

The five-firm directory refresh validated extraction and publication. Profile enrichment was checked separately. The firm-by-firm evidence and outstanding source failures are in the [assessment review](ASSESSMENT_REVIEW.md).

## 6. Prioritise reliability before expanding to 50 or 100 firms

The refresh now preserves the last verified data for a failed firm while updating successful firms. For production I would add visible freshness, per-firm run history, and alerts for unusual count changes or failures. An orchestration tool such as Google Cloud Composer could invoke the existing refresh command weekly as a scheduled job, with overlap protection and a persistent database accessible to both the job and the API. Enrich new or stale profiles with bounded per-site requests. I would measure freshness, runtime, payload size, and SQLite contention before moving search to the server or introducing a shared database. [Google Cloud scheduling guide](https://docs.cloud.google.com/composer/docs/composer-3/schedule-and-trigger-dags)

A larger registry alone still leaves someone learning every site. I would test bulk onboarding from a firm name and optional homepage. Discovery would propose the official domain, directory, and practice team pages from site navigation, sitemaps, and search. Where it can establish a complete set of profile links, it can classify roles and practices from the profiles. That avoids depending on a separate practice-search implementation for every firm. Where a source supplies totals, compare them with unique profiles fetched. Compare independent official sources when possible and record when the evidence is insufficient.

Shared HTML and JSON extractors can absorb common request, response, and pagination patterns. A discovery assistant could also propose draft settings or draft a small extractor for a source it can inspect. A reviewer would check scope and coverage before enabling the source. I would test this on one known firm and one new firm and measure how much manual investigation it replaces. Approved configurations can then run weekly and go back to review on unexpected changes. A licensed dataset is another option if the business needs broad coverage sooner than it can verify sources itself.

For responsible collection at that scale, I would review site access terms and crawler rules before onboarding, make requests identifiable and bounded per domain, and stop when access is blocked. I would retain the professional fields the recruiter needs, attach evidence and observation times, and set retention and correction rules before sharing the system more widely. These are production measures to implement alongside scheduling and source monitoring.
