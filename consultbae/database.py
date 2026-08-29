"""SQLite schema and database helpers."""
from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS persons (
  id INTEGER PRIMARY KEY, canonical_name TEXT NOT NULL, normalized_email TEXT UNIQUE,
  normalized_phone TEXT UNIQUE, normalized_city TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS source_records (
  id INTEGER PRIMARY KEY, source_name TEXT NOT NULL, source_row INTEGER NOT NULL,
  source_key TEXT NOT NULL UNIQUE, raw_json TEXT NOT NULL, valid INTEGER NOT NULL DEFAULT 1,
  ingestion_error TEXT, person_id INTEGER REFERENCES persons(id), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_name, source_row)
);
CREATE TABLE IF NOT EXISTS field_provenance (
  id INTEGER PRIMARY KEY, person_id INTEGER NOT NULL REFERENCES persons(id),
  source_record_id INTEGER NOT NULL REFERENCES source_records(id), field_name TEXT NOT NULL,
  raw_value TEXT, normalized_value TEXT, UNIQUE(source_record_id, field_name)
);
CREATE TABLE IF NOT EXISTS identity_decisions (
  id INTEGER PRIMARY KEY, source_record_id INTEGER NOT NULL UNIQUE REFERENCES source_records(id),
  person_id INTEGER REFERENCES persons(id), match_rule TEXT NOT NULL, confidence TEXT NOT NULL, notes TEXT
);
CREATE TABLE IF NOT EXISTS audio_submissions (
  id INTEGER PRIMARY KEY, person_id INTEGER NOT NULL REFERENCES persons(id), original_filename TEXT NOT NULL,
  stored_path TEXT NOT NULL, duration_seconds REAL, sample_rate_khz REAL, bitrate_kbps REAL,
  loudness_dbfs REAL, audio_format TEXT, analyzer TEXT, analysis_error TEXT,
  submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_source_records_person ON source_records(person_id);
CREATE INDEX IF NOT EXISTS idx_audio_person ON audio_submissions(person_id);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
