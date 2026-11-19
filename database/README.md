# SQLite database

The refresh creates `database/partners.db` and applies pending migrations.
To initialize the schema without scraping, run this from the repository root:

```powershell
.\.venv\Scripts\python.exe -c "from pipeline.storage.sqlite_database import SQLiteDatabase; SQLiteDatabase()"
```

| Table | Contents |
|---|---|
| `scraped_raw_<firm_key>` | Latest connector records before normalization and deduplication |
| `scraped_raw_runs` | Latest extraction status, coverage, counts, and warnings per firm |
| `partner_entries_<firm_key>` | Latest complete, scope-verified roster for one firm |
| `partner_entries_all` | Combined verified rosters, explicitly allowed partial entries, and retained removals |
| `partner_profiles_all` | Enriched profiles keyed by `partner_entry_id`; untouched current profiles survive limited or partial enrichment |
| `partner_profile_failures_all` | Failures from the latest enrichment stage |

List fields such as offices and practices are stored as JSON arrays. Git tracks
the migration SQL and ignores the local SQLite database. The files under
`mock_database/` are snapshots from the earlier JSON storage workflow.

Filter on `no_longer_listed_at IS NULL` for the current combined roster.
When a complete, verified combined refresh omits an entry for one of the
refreshed firms, the pipeline sets this timestamp and retains the stored profile.
If the entry reappears, the pipeline clears the timestamp. Profile enrichment
reads current entries eligible for publication in that run. An explicitly
allowed partial import adds or updates observed entries without marking
absent partners as removed. A failed firm keeps its prior roster and profiles.
