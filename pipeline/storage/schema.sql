PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS partners (
    id INTEGER PRIMARY KEY,
    partner_entry_id TEXT NOT NULL UNIQUE,
    firm_key TEXT NOT NULL,
    firm_name TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    profile_url TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_record_id TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    last_checked_at TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    UNIQUE (firm_key, profile_url)
);

CREATE TABLE IF NOT EXISTS partner_offices (
    partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
    office TEXT NOT NULL,
    UNIQUE (partner_id, office)
);

CREATE TABLE IF NOT EXISTS partner_practices (
    partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
    practice TEXT NOT NULL,
    UNIQUE (partner_id, practice)
);

CREATE TABLE IF NOT EXISTS refresh_runs (
    id INTEGER PRIMARY KEY,
    firm_key TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    records_extracted INTEGER NOT NULL DEFAULT 0,
    records_loaded INTEGER NOT NULL DEFAULT 0,
    pages_fetched INTEGER NOT NULL DEFAULT 0,
    message TEXT
);
