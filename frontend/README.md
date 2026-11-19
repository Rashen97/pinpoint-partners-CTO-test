# Partner directory frontend

From the repository root, serve the frontend with Python:

```powershell
python -m http.server 8080 --bind 127.0.0.1 --directory frontend
```

Open [the local directory](http://127.0.0.1:8080/). It connects to the local
FastAPI backend on port 8001 by default. Start the backend as described in the
[project README](../README.md). For a standalone sample preview, set the
`api-base` meta tag in `index.html` to an empty string. Saved partners are
stored in the current browser.
Recent changes includes a fictional sample preview that opens automatically
when there are no live changes. The research form starts blank
on sample profiles. On a connected roster, open a
partner profile to edit a name-and-firm query or add a topic, then open Google
in a new tab. Google receives the query when the recruiter submits it.

## Connect a backend

Set the `api-base` meta tag in `index.html` to `/api` for a same-origin backend,
or to an absolute URL such as `http://localhost:8000/api` for a separate server.
If using a separate server, allow the frontend origin through CORS.
`api.js` contains the HTTP adapter.

### `GET /api/partners`

Return JSON with a `records` array containing active partners with saved profile enrichment.
The frontend applies search, firm/office/practice filters, name sorting, and
pagination to this collection.

```json
{
  "records": [
    {
      "partner_entry_id": "a-stable-pipeline-entry-id",
      "firm_key": "example_firm",
      "firm_name": "Example Firm",
      "name": "Alex Morgan",
      "role": "Partner",
      "offices": ["London"],
      "practices": ["Corporate", "Mergers and Acquisitions"],
      "profile_url": "https://example.com/people/alex-morgan"
    }
  ]
}
```

Use unique, stable `partner_entry_id` values and return an empty array for
missing offices or practices. An empty directory returns `{"records":[]}`.
With an API base configured, a request error is displayed in the directory.

The response can also include coverage and changes when the backend has
verified observations:

```json
{
  "records": [],
  "coverage": { "verified_firm_count": 2, "target_firm_count": 15 },
  "changes": [
    {
      "name": "Alex Morgan",
      "firm_name": "Example Firm",
      "kind": "no_longer_listed",
      "observed_at": "2026-11-16",
      "source_url": "https://example.com/people"
    }
  ]
}
```

Supported change kinds are `newly_listed` and `no_longer_listed`. Use the
verified observation date and optionally include the source roster URL. Omit
`changes` when history is unavailable and send an empty array when the
available history contains no events.

### `GET /api/partners/{partner_entry_id}`

Return the enriched profile as a JSON object with any available fields from
`PartnerProfileInfo`. The drawer displays `biography`, `email`, `phone_numbers`,
`education`, `admissions`, `languages`, and the ISO `source_checked_at` timestamp.
Return HTTP 404 if enrichment is unavailable. The drawer can still display the
roster entry and its firm profile link.

## Visual references

- [Pinpoint Partners](https://pinpoint-partners.com/) inspired the red accent and executive-search tone.
- [Skyline photograph](https://images.unsplash.com/photo-1518391846015-55a9cc003b25) via Unsplash.
