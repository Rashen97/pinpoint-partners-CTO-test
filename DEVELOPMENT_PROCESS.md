# Development Process

This document explains how I approached the project, the reasoning behind my decisions, and how I structured the solution within the six-hour time limit.

## Design decision log

### Separate directory extraction from profile enrichment

My initial thinking for the scraping pipeline was to first create a unified list of partner entries from all of the firms. Although each firm exposes its directory differently, every connector should return the same target structure. I called this structure `PartnerEntryInfo` because it represents the information available in a firm's directory entry: the partner's name, role, offices, native practice labels, profile URL, and source information.

I then realised that this unified list is an intermediate dataset rather than the finished partner dataset. The firm directories establish who is listed as a relevant partner and provide the profile URLs, but much of the useful information for a recruiter is only available after opening each individual profile. That can include the full biography, more detailed practice descriptions, education, admissions, contact details, languages, representative work, and other source-backed facts.

My proposed design is therefore to write a second script that consumes the saved `PartnerEntryInfo` records, iterates over their profile URLs, and performs a deeper profile scrape. The first script answers *who is in the roster?*; the second answers *what does the firm's profile tell us about this person?*

I chose to keep these as separate stages because roster extraction and profile enrichment have different reliability and scheduling requirements. A failed biography request should not invalidate an otherwise successful roster refresh or make a partner appear to have left the firm. Directory listings can be refreshed weekly, while existing profiles can be refreshed less frequently or only when they become stale. New partner entries can be enriched immediately. Keeping the stages separate also makes failures easier to retry and explain.

The intended flow is:

```text
firm directories
    -> PartnerEntryInfo records
    -> validation and deduplication
    -> roster database
    -> separate profile-enrichment script
    -> PartnerProfileInfo records
    -> enriched partner database
```

The directory connector remains the authority for roster membership. The profile connector enriches a roster entry but does not decide whether the person is currently listed. If a profile page fails or returns 404, that should be recorded as an enrichment failure rather than interpreted as a departure.

This decision also keeps the model honest. `PartnerEntryInfo` contains only directory-supported facts. A separate `PartnerProfileInfo` model can contain profile-supported facts and its own source URL, checked timestamp, and content hash. AI-generated summaries or external research would be another downstream layer rather than being mixed into either source model.

This document should continue to capture design ideas, decisions, alternatives, and reasoning as they arise during development, including ideas introduced during discussion rather than only completed implementation work.

### Enrich the unified dataset rather than orchestrating firm-by-firm profile jobs

I refined the profile-enrichment design after considering where the firm-specific boundary should sit. The directory connectors still need to be firm-specific because each firm exposes its roster through different requests, filters, pagination, and response formats. However, their purpose is to transform those different sources into one unified collection of `PartnerEntryInfo` records.

Once that transformation has happened, the next script should operate on the entire unified dataset. It should iterate through the entries, follow each `profile_url`, and produce profile-enrichment records regardless of which directory connector originally produced them. The enrichment runner therefore does not need a separate orchestration script or top-level connector file for every firm.

Individual profile pages will still have different HTML structures, so some firm-specific parsing knowledge remains necessary. My preferred compromise is one shared profile fetch-and-parse framework with selectors and field mappings stored as configuration. Firms that share a conventional HTML shape can use that framework directly. A custom parser should only be introduced when a firm's page cannot be represented safely through the common configuration. This avoids creating fifteen nearly identical profile connector files while still acknowledging that one universal set of CSS selectors cannot parse every website reliably.

The revised boundary is:

```text
firm-specific directory connectors
    -> unified PartnerEntryInfo dataset
    -> one dataset-wide enrichment runner
    -> shared profile fetcher and configurable parser
    -> optional custom parser for genuine exceptions
    -> PartnerProfileInfo dataset
```

### Keep `refresh.py` as the single pipeline entry point

I clarified that the dataset-wide profile enrichment should not become a second user-facing command. It is a stage within the overall refresh workflow and should therefore be orchestrated by `refresh.py`, alongside extraction, normalization, validation, and database loading. The shared enrichment implementation belongs in an internal pipeline module, while `refresh.py` decides when it runs and how its result affects the overall refresh status.

This keeps one operational command for a scheduled refresh and avoids making a user manually export directory JSON and pass it into another script. A directory-only option can remain as a development and debugging control, but the normal refresh path should continue from validated `PartnerEntryInfo` records into profile enrichment automatically. Profile failures are reported separately and must not invalidate or erase the successfully extracted roster.

### Group profile enrichment into its own package

I decided that the root of the `pipeline` package should remain focused on orchestration and small helpers used directly by orchestration. Although profile enrichment is invoked by `refresh.py`, its implementation is a distinct concern with its own fetching, parsing, configuration, result types, and tests. Leaving those modules spread across the pipeline root would make the orchestration layer increasingly difficult to scan as enrichment grows.

The profile-specific implementation should therefore be grouped under `pipeline/profile_enrichment/`. The package can contain the dataset-wide enrichment service, the shared profile fetcher/parser, selector configuration loading, and any future custom parsing exceptions. `pipeline/refresh.py` remains responsible for deciding when the stage runs and for combining its result with the rest of the refresh outcome.

The intended boundary is:

```text
pipeline/
    refresh.py                 # orchestration
    config.py                  # orchestration/source configuration helper
    models.py                  # shared pipeline contracts
    connectors/                # directory extraction
    processing/                # shared roster transformation/validation
    storage/                   # persistence
    profile_enrichment/
        service.py             # iterate the unified entry dataset
        connector.py           # fetch and parse profile pages
        config.py              # load profile selector mappings
        profile_sources.yaml   # firm-specific selector configuration
```

This does not make profile enrichment a separate command. It remains an internal stage orchestrated by `refresh.py`; the folder only gives that stage a clear implementation boundary.

### Use a local JSON folder as a temporary database

Before introducing a real database, I decided to make the pipeline stages visible and inspectable by storing their outputs as JSON in a root-level `mock_database/` folder alongside `pipeline/`. This provides a simple stand-in for persistence while the extraction and transformation contracts are still evolving.

The first persisted stage is the connector extraction. This captures what the connector returned before shared normalization and deduplication, which makes source and parser problems easier to inspect. The second persisted stage is the unified `PartnerEntryInfo` dataset produced after shared transformation.

The two outputs have different safety rules. A connector extraction may be saved for diagnostics even when its coverage is incomplete. The unified roster file represents the latest good dataset and must only be replaced after extraction completes and the Corporate/M&A scope is verified. This preserves the earlier rule that a blocked, partial, or malformed refresh must not look like a departure.

JSON writes should be atomic: write a temporary file in the destination folder and replace the stage file only after serialization succeeds. Generated datasets remain local and ignored by Git, while the `mock_database/README.md` and empty folder structure document the intended collections.

### Make the default refresh run every currently viable connector

I clarified that the normal `python -m pipeline.refresh` command should orchestrate all connectors that currently satisfy the project requirement, rather than requiring one `--firm` invocation at a time. A targeted firm option remains useful for development and diagnosis, but the operational default should build the market-wide dataset.

“Working” means more than an endpoint returning data. A connector is enabled for the default production-style refresh only when its Corporate/M&A scope and pagination are sufficiently verified. Paul Weiss and Simpson Thacher currently meet that standard. Sullivan & Cromwell remains available as a targeted partial connector because its M&A source works but a broad Corporate filter is missing. Kirkland and Wachtell remain targeted diagnostics because their sources currently fail or block automated access.

The all-firm refresh must isolate firm failures and report a per-firm status. It may update each successful firm's latest good file independently, but it must only replace the combined `all_partners.json` dataset when every connector selected for that all-firm run produced a complete, verified roster. This prevents a single failed firm from silently disappearing from the combined dataset.

### Run firm extraction sequentially, then enrich the combined dataset

I clarified the exact orchestration order for the all-firm refresh. Firm connectors should run one by one. Each connector extraction is saved, transformed into `PartnerEntryInfo`, validated, and added to an in-memory collection of successful firm datasets. Only after every selected firm has completed should those datasets be joined into one unified partner-entry collection and saved as `all_partners.json`.

Profile enrichment should then run once over that combined collection. It should not be interleaved inside the per-firm extraction loop, because the conceptual input to enrichment is the unified market dataset rather than an individual firm's temporary result. This also gives the stages a clearer order and makes their counts and failures easier to report:

```text
firm A extract -> transform -> validate -> collect
firm B extract -> transform -> validate -> collect
...
join all successful verified PartnerEntryInfo records
save all_partners.json
iterate the combined dataset for profile enrichment
```

The connectors remain sequential for predictable load, simpler source debugging, and clearer failure isolation. Parallel extraction could be introduced later, but it is not necessary for this prototype and would make respectful request pacing harder to reason about.

### Give each roster entry an internal ID without claiming cross-firm identity

I identified that the unified dataset needs an internal identifier for each partner entry. Firm-provided IDs are not available or reliable across every source, and names are not safe identifiers. The initial source identity is therefore the combination of `firm_key` and canonical `profile_url`, which is already the pipeline's deduplication key.

The internal field should be called `partner_entry_id` rather than implying that it is a permanent global identity for the human being. A deterministic UUID can be generated from a fixed application namespace plus `firm_key` and the canonical profile URL. That produces the same ID on repeated refreshes without requiring an auto-incrementing database and avoids exposing the URL as the identifier.

I considered generating this ID during profile enrichment, but decided that point is too late. The ID belongs to the unified `PartnerEntryInfo` contract and should exist before the dataset is saved to `all_partners.json`. It is therefore generated in the shared normalization/transformation stage after the profile URL has been canonicalized. Profile enrichment consumes the ID and copies it into `PartnerProfileInfo`, giving the profile record a stable reference back to its roster entry.

This ID remains scoped to a firm's roster entry. If a person changes firms, the new firm entry should initially receive a new ID. The system must not merge people across firms by name alone. A later identity-resolution layer could introduce a separate `person_id`, supported by stronger evidence and a table of source aliases. Similarly, if a firm changes a profile URL, the first implementation may generate a new entry ID; preserving identity across URL changes would require retaining old source URLs or firm source IDs as aliases.

### Keep one refresh command and make limited runs easy to reproduce

I removed the repository-root wrapper so that `pipeline/refresh.py` is the single entry point. Running `python -m pipeline.refresh` from the project root keeps the command aligned with the Python package layout. I added PowerShell examples at the top of the module so I can run the same checks from the editor with the project's virtual environment.

I wanted to exercise the entire flow across the enabled firms without waiting for every profile request. The default run attempts profile enrichment for the whole current combined roster. `--profile-limit 10` still extracts the full directories and caps enrichment at ten entries across the combined roster. `--directory-only` exercises the directory and storage stages. A targeted `--firm` run is useful for diagnosing one directory connector and stops before combined enrichment.

### Move stage storage from JSON to SQLite

I used the JSON snapshots to inspect the intermediate datasets before settling on the database structure. Once the shapes were clear, I moved the old snapshots into `mock_database/` and switched refreshes to `database/partners.db`. SQLite fits the local prototype because Python can create and open the database file without a separate service. The schema belongs in versioned SQL under `database/migrations/`. The committed migrations let a new checkout recreate the tables, and the generated database stays local.

I kept responsibility for writes in `pipeline/storage/` because the ingestion pipeline knows the completeness and scope of each refresh. When I add a backend, its queries can live with the API code and read the same schema. The frontend will get its data through that API. If the pipeline and backend eventually run on separate machines, the same ownership split can carry over to a shared server database.

### Name tables after the stage and the data they hold

I wanted to be able to open SQLite and see what each stage produced. `scraped_raw_<firm>` stores the connector's output before shared normalization and deduplication. The connector may already have merged overlapping source results by that point. `partner_entries_<firm>` stores the latest complete, verified roster for that firm. `partner_entries_all` publishes the combined roster after every enabled firm succeeds. Keeping a firm-level copy lets a successful firm save its work even if the combined refresh is held back. Profile enrichment then reads the current combined roster and writes to `partner_profiles_all`, with `partner_entry_id` linking the two tables.

I asked where each table was created and removed the temporary rename statements once the final names were decided. The migrations create the shared tables directly. The storage layer creates a per-firm table when that firm's stage is first written. The active `scraped_raw_runs` table holds the latest extraction metadata per firm, including page counts, coverage and warnings. An earlier `refresh_runs` design would have stored a history of attempts. Partner fields and biographies live in the stage tables, and recent profile failures have their own diagnostic table.

### Make repeated profile loads and roster removals safe

I expect this pipeline to run on a schedule eventually, so I wanted repeated runs to add new profiles, update changed profiles, and leave identical profiles alone. Storage uses `partner_entry_id` to find the row and a hash of the extracted profile fields to detect a content change. This allows changes to fields such as education, admissions and languages to trigger an update. After fetching and parsing the profile, storage skips an identical row and rejects incoming content older than the stored version. A limited enrichment run preserves previously stored profiles for current roster entries.

I chose to retain missing roster entries and their last saved profiles. When a complete, verified combined refresh omits an entry for a refreshed firm, the database sets `no_longer_listed_at`. The directory and profile enrichment can use entries where that value is empty. If the same entry returns, the refresh clears the timestamp. A failed scrape, partial roster or profile error provides insufficient evidence to change listing status. An omission supports calling someone “no longer listed”.

### Check directory coverage and enrichment separately

When the full refresh stopped, I checked SQLite and the live connector results separately. The saved Paul Weiss data contained 216 unique partners across the Corporate and M&A directory filters. The ten saved profiles came from a limited enrichment run, so the profile count measured how far enrichment had gone and the roster count measured directory coverage.

Simpson Thacher's legacy endpoint failed during the combined refresh. I kept the last verified combined roster and left the replacement source pending verification of both practice filters and pagination. I also tested the disabled connectors directly. Sullivan & Cromwell returned 94 M&A partners and still lacked verified broad Corporate coverage. Kirkland returned HTTP 500, and Wachtell returned HTTP 403. These checks showed why connector availability, verified scope and profile coverage each need their own status.

## Understanding the problem

I started by reading the brief carefully so that I understood both what needed to be built and who it was being built for. Once I had understood the requirements, I uploaded the brief to ChatGPT and used it as a brainstorming partner to explore possible approaches.

My first consideration was how a recruiter would actually use the information. A chatbot on its own could answer individual questions, but I felt that relying entirely on chat would quickly become tedious. A recruiter may need to review and compare a large number of lawyers, and doing that through a long series of separate conversations would make the information difficult to scan and organise.

This led me to the idea of making a structured directory the main interface. A directory gives recruiters an organised way to search, filter, browse, and compare the information that has already been collected. It makes the core data easy to access without requiring the recruiter to know exactly what question to ask.

I still saw value in a chat system alongside the directory. My idea was for this to use an agentic model with tools and web-scraping or search connectors. If information had not already been captured in the directory, the assistant could look for it at runtime and return it to the recruiter. It could also support a natural back-and-forth conversation when the recruiter wanted to explore a person or topic in more detail. In this design, the directory provides the reliable and organised foundation, while the assistant adds flexibility for questions that the stored data cannot answer.

## Starting with the data

Once I had decided on the product direction, I thought about the first practical requirement: the data. The directory and any future assistant would only be useful if the underlying information could be collected reliably.

I visited the websites for each firm in the brief and investigated how their lawyer or attorney directories worked. I looked at the pages themselves as well as their network requests and source code to understand where the results came from and how they might be scraped. The firms did not all expose their information in the same way: some used HTML responses, while others used JSON endpoints, form requests, or more dynamic search services.

I recorded what I discovered in `pipeline/firms.yaml`, including details such as request URLs and the relevant source configuration. This gave me a central place to capture firm-specific knowledge rather than spreading it throughout the code. It also allowed me to separate the question of *where the data comes from* from the code that fetches and processes it.

## Designing for continued use

After identifying the data sources, I began designing the codebase structure. I did not want to treat the project as a collection of one-off scraping scripts. If this application were developed for long-term use, the process of scraping, cleaning, validating, and uploading the data to a database would need to run repeatedly on a schedule.

In a production system, I would expect that workflow to be scheduled and monitored through an orchestration tool. Implementing a full orchestration platform was not the best use of the six-hour assessment window, so I deliberately left that out. However, I structured the pipeline so that orchestration could be added later without requiring the scraping and processing code to be reorganised.

The pipeline structure reflects that decision. `refresh.py` is the main entry point and orchestrates a refresh. The `pipeline/connectors` directory contains the firm-specific scraping connectors, while the remaining pipeline modules handle shared concerns such as processing, validation, and storage. This means a future scheduler could invoke the same refresh workflow rather than requiring a separate implementation.

I used AI to help me build parts of the connector code, particularly where different websites required different request and parsing logic. I did not treat the generated code as automatically correct: I reviewed it, ran it, and validated its behaviour against the firm websites and the responses I had inspected. This let me use AI to work faster while keeping responsibility for understanding and verifying the submitted code.

Overall, my approach was to begin with the recruiter's workflow, choose an interface that made the information manageable, and then work backwards to the data pipeline needed to support it. I also tried to balance the short time limit with a structure that could realistically be extended into a scheduled, maintainable system.
