CREATE TABLE profile_enrichment_status (
    firm_key TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('complete', 'partial', 'rate_limited')),
    checked_at TEXT NOT NULL,
    retry_at TEXT
);
