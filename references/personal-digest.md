# Personal incremental digest extension

This fork reuses the upstream RSS fetcher and adds a deterministic collector and SQLite delivery ledger. It does not call an LLM, connect private accounts, schedule itself, or write to Apple applications. Those responsibilities remain in the local host integration. The upstream MIT license is retained.

## Entry points

- `scripts/personal_collect.py`: collect only explicitly configured RSS and public page sources, with conditional HTTP caching and source-specific errors.
- `scripts/personal_digest.py`: validate confirmed preferences, ingest content versions, prepare an immutable pending batch, and acknowledge verified delivery.
- `tests/test_personal_digest.py`: regression coverage for opt-in sources, disabled sources, crash/restart, unchanged cache, changed versions, primary/fallback ranking, stale entries, receipt validation, and Adelaide daylight saving.

Install `feedparser` and `beautifulsoup4` in a virtual environment. Use each script's `--help` for arguments. Profile, SQLite state, downloaded pages and delivery receipts belong outside the repository.

Example profile:

```json
{
  "selection_status": "confirmed",
  "categories": ["E", "F", "D", "A", "B", "C"],
  "primary_categories": ["E", "F", "D"],
  "timezone": "Australia/Adelaide",
  "mode": "review_queue",
  "max_items": 20,
  "lookback_days": 7,
  "sources": [
    {"id": "bbc-world", "name": "BBC World", "type": "rss", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "categories": ["F"], "enabled": true}
  ]
}
```

Category mapping: A AI and automation; B English; C secondary teaching; D migration; E Australian life; F world news; G Apple/development; H business/productivity; I science/other interests. Source enablement is intersected with selected categories. HTTP failures remain distinct from successful checks with no new articles. Unknown page dates remain unknown, so the editor must check the source before claiming fresh news.

An HTTP cache is not a delivery ledger. A prepared batch survives restarts until the consumer supplies a verified target receipt. Consumers must make destination writes idempotent using the batch ID, and acknowledge only after reading the destination back. Excluded candidates should be recorded with reasons so rejected content is not repeatedly proposed. Cross-source duplicate stories require editorial consolidation; URL/version deduplication alone does not establish semantic equivalence.

This collector cannot guarantee that upstream information is accurate or that an unknown-date page represents a new announcement. Verify migration decisions and shopping availability against current primary sources. No private profile, email, calendar identifier, credential, or production database is included in this fork.
