CREATE TABLE firm_roster_baselines (
    firm_key TEXT PRIMARY KEY
);

INSERT INTO firm_roster_baselines (firm_key)
SELECT DISTINCT firm_key
FROM partner_entries_all
WHERE scope_verified = 1;

CREATE TABLE partner_roster_events (
    event_id INTEGER PRIMARY KEY,
    partner_entry_id TEXT NOT NULL,
    firm_key TEXT NOT NULL,
    firm_name TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('newly_listed', 'no_longer_listed', 'relisted')),
    observed_at TEXT NOT NULL,
    source_url TEXT NOT NULL
);

INSERT INTO partner_roster_events (
    partner_entry_id, firm_key, firm_name, name, kind, observed_at, source_url
)
SELECT partner_entry_id, firm_key, firm_name, name, 'no_longer_listed',
       no_longer_listed_at, source_url
FROM partner_entries_all
WHERE scope_verified = 1 AND no_longer_listed_at IS NOT NULL;

CREATE TABLE confirmed_partner_moves (
    departure_event_id INTEGER PRIMARY KEY REFERENCES partner_roster_events (event_id),
    addition_event_id INTEGER NOT NULL UNIQUE REFERENCES partner_roster_events (event_id),
    evidence_url TEXT NOT NULL,
    confirmed_at TEXT NOT NULL,
    effective_on TEXT
);

CREATE INDEX partner_roster_events_by_entry
ON partner_roster_events (partner_entry_id, event_id);
