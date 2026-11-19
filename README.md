# Pinpoint partner directory

The refresh pipeline is organized as `connectors -> processing -> storage`.
The current prototype runs the refresh pipeline with a local JSON mock
database. Every connector returns `PartnerEntryInfo` records while retaining
native firm role, office, and practice labels.

```powershell
python -m pip install -r requirements.txt
python -m pipeline.refresh --firm paul_weiss
python -m pipeline.refresh --firm simpson_thacher
python -m pipeline.refresh --firm sullivan_cromwell --include-unverified-scope
python -m pipeline.refresh --firm kirkland
python -m unittest discover -s pipeline/tests -v
```

Refresh commands print JSON and save pipeline outputs in `mock_database/`.
See the [mock database guide](mock_database/README.md) for the snapshot layout.

By default, `refresh.py` continues from directory extraction into profile
enrichment across the unified `PartnerEntryInfo` dataset:

```powershell
python -m pipeline.refresh
```

The default run refreshes every currently complete, verified connector. Use
`--firm` only for targeted development or diagnosis.

For development, limit enrichment or stop after directory extraction:

```powershell
python -m pipeline.refresh --profile-limit 10
python -m pipeline.refresh --directory-only
```

The internal enrichment stage iterates the unified dataset. One shared HTML
profile connector reads firm-specific selector mappings from
`pipeline/profile_enrichment/profile_sources.yaml`; a separate profile connector file is not
created for every firm.

Profile enrichment begins after every selected directory connector produces
a complete, verified roster. It reads `mock_database/partner_entries/all_partners.json`
and writes profiles and enrichment failures to `mock_database/partner_profiles/all_profiles.json`.

## Connector status

| Firm | Current status | Coverage |
|---|---|---|
| Paul Weiss | Live verified | Corporate and Mergers and Acquisitions |
| Simpson Thacher | Live verified | Corporate and Mergers and Acquisitions |
| Sullivan & Cromwell | Live, intentionally partial | Mergers & Acquisitions; broad Corporate filter missing |
| Wachtell Lipton | Implemented, runner blocked by HTTP 403 | Corporate rule; no general M&A option published |
| Kirkland & Ellis | Implemented against captured JSON, source currently failing | Corporate/M&A filters unverified |

Counts are observations from a refresh, not constants. A partial or blocked
connector must not be loaded as a complete roster.

The live Kirkland endpoint currently returns an error page to a direct request.
The connector checks for JSON and fails rather than interpreting that response
as an empty directory.
