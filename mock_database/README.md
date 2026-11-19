# Local JSON database

This folder contains snapshots from the earlier JSON storage workflow.
Current refreshes write to SQLite. See [the SQLite table guide](../database/README.md).

Collections:

- `connector_extractions/`: latest connector output before shared processing.
- `partner_entries/`: latest complete, scope-verified `PartnerEntryInfo` dataset.
- `partner_profiles/`: profile enrichment produced from the unified `all_partners.json` input.

Generated JSON files are local runtime data and are ignored by Git. Connector
extractions are diagnostic artifacts. Files in `partner_entries` are protected:
an incomplete or unverified refresh must not replace the last good dataset.
The combined `partner_entries/all_partners.json` file is replaced only when
every connector selected by the default all-firm refresh succeeds.
Profile enrichment reloads that combined file as its input contract and writes
`partner_profiles/all_profiles.json`.
