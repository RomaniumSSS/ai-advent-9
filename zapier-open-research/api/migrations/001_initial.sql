CREATE TABLE IF NOT EXISTS saved_works (
  openalex_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  doi TEXT,
  publication_date DATE,
  primary_source TEXT,
  open_access_url TEXT,
  score INTEGER CHECK (score BETWEEN 0 AND 100),
  score_explanation TEXT,
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS saved_works_doi_unique
  ON saved_works (LOWER(doi)) WHERE doi IS NOT NULL;

CREATE TABLE IF NOT EXISTS webhook_subscriptions (
  id UUID PRIMARY KEY,
  target_url TEXT NOT NULL,
  event TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS review_ledger (
  id UUID PRIMARY KEY,
  idempotency_key TEXT NOT NULL UNIQUE,
  openalex_id TEXT NOT NULL REFERENCES saved_works(openalex_id),
  score INTEGER NOT NULL CHECK (score BETWEEN -100 AND 100),
  source_event_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
