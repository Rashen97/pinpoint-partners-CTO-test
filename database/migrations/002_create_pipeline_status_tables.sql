CREATE TABLE scraped_raw_runs (
    firm_key TEXT PRIMARY KEY NOT NULL,
    saved_at TEXT NOT NULL,
    pages_fetched INTEGER NOT NULL,
    expected_total INTEGER,
    extraction_complete INTEGER NOT NULL,
    scope_verified INTEGER NOT NULL,
    covered_practices TEXT NOT NULL,
    missing_practices TEXT NOT NULL,
    warnings TEXT NOT NULL
);

CREATE TABLE partner_profile_failures_all (
    firm_key TEXT NOT NULL,
    profile_url TEXT NOT NULL,
    error TEXT NOT NULL
);
