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

CREATE TABLE IF NOT EXISTS worker_state (
  key TEXT NOT NULL PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_monitor_records (
  record_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  group_id TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 1,
  filename TEXT NOT NULL,
  pm_fingerprint TEXT NOT NULL DEFAULT '',
  pm TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  last_activity_at TEXT NOT NULL,
  target_language TEXT NOT NULL DEFAULT '',
  total_count INTEGER NOT NULL DEFAULT 0,
  requested_count INTEGER NOT NULL DEFAULT 0,
  cached_count INTEGER NOT NULL DEFAULT 0,
  failed_count INTEGER NOT NULL DEFAULT 0,
  model TEXT NOT NULL DEFAULT '',
  app_version TEXT NOT NULL DEFAULT '',
  error_category TEXT NOT NULL DEFAULT '',
  expected_languages_json TEXT NOT NULL DEFAULT '[]',
  feishu_record_id TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_review_monitor_updated
ON review_monitor_records (updated_at);
