CREATE TABLE IF NOT EXISTS partner_entries_all (
    partner_entry_id TEXT PRIMARY KEY NOT NULL,
    firm_key TEXT NOT NULL,
    firm_name TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    offices TEXT NOT NULL,
    practices TEXT NOT NULL,
    profile_url TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_record_id TEXT,
    UNIQUE (firm_key, profile_url)
);

CREATE TABLE IF NOT EXISTS partner_profiles_all (
    partner_entry_id TEXT PRIMARY KEY NOT NULL
        REFERENCES partner_entries_all (partner_entry_id),
    role TEXT,
    offices TEXT NOT NULL,
    practices TEXT NOT NULL,
    biography TEXT,
    phone_numbers TEXT NOT NULL,
    email TEXT,
    education TEXT NOT NULL,
    admissions TEXT NOT NULL,
    languages TEXT NOT NULL,
    source_checked_at TEXT NOT NULL,
    content_hash TEXT NOT NULL
);
