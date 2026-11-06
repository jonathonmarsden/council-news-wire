// The edge's copy of what the bot has published: one row per story, keyed by
// the council's own URL; `uri` is the Bluesky post when there is one.
// Idempotent; run before each ingest so a fresh database needs no setup step.
export const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS posts (
     url TEXT PRIMARY KEY, uri TEXT, council_id TEXT NOT NULL, council_name TEXT NOT NULL,
     state TEXT NOT NULL, title TEXT NOT NULL, excerpt TEXT, published_at TEXT, posted_at TEXT NOT NULL)`,
  "CREATE INDEX IF NOT EXISTS posts_council_posted ON posts (council_id, posted_at DESC)",
  "CREATE INDEX IF NOT EXISTS posts_state_posted ON posts (state, posted_at DESC)",
  "CREATE INDEX IF NOT EXISTS posts_posted ON posts (posted_at DESC)",
];
