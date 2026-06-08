CREATE TABLE IF NOT EXISTS event_counts (
  event_date TEXT NOT NULL,
  event_name TEXT NOT NULL,
  app_version TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (event_date, event_name, app_version)
);

CREATE INDEX IF NOT EXISTS idx_event_counts_name_date
ON event_counts (event_name, event_date);
