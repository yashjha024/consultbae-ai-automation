"""Re-runnable CSV ingestion and conservative entity resolution."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from pathlib import Path

from .database import connect
from .normalization import normalize_city, normalize_email, normalize_name, normalize_phone, normalize_skills, normalize_status

SOURCE_MAP = {
    "naukri": {"path": "source1_naukri_applicants.csv", "name": "Full Name", "email": "Email", "phone": "Phone", "city": "City", "status": None, "skills": "Skills"},
    "gig_workers": {"path": "source2_gig_workers.csv", "name": "worker_name", "email": "email_id", "phone": None, "city": "location", "status": "status", "skills": "skill_tags"},
    "cbnexus": {"path": "source3_cbnexus_contacts.csv", "name": "Name", "email": None, "phone": "Phone Number", "city": "City", "status": "Verified", "skills": None},
}


def _value(row: dict, key: str | None) -> str | None:
    return row.get(key) if key else None


def normalized_record(source: str, row: dict) -> dict:
    config = SOURCE_MAP[source]
    return {"name": normalize_name(_value(row, config["name"])), "email": normalize_email(_value(row, config["email"])),
            "phone": normalize_phone(_value(row, config["phone"])), "city": normalize_city(_value(row, config["city"])),
            "status": normalize_status(_value(row, config["status"])), "skills": normalize_skills(_value(row, config["skills"]))}


def _row_error(source: str, row: dict) -> str | None:
    if None in row:
        return "CSV has more values than its header; row is shifted/malformed and was not matched."
    if source == "cbnexus" and row.get("Name") == "Name" and row.get("Phone Number") == "Phone Number":
        return "Repeated header row embedded in data; retained as invalid source record."
    if source == "gig_workers" and not any((row.get("email_id") or "").strip() for _ in [0]):
        return "Blank separator row; retained as invalid source record."
    if source == "gig_workers" and not normalize_email(row.get("email_id")):
        return "Column-shifted/malformed row: email_id is not an email; retained but not matched."
    return None


def _source_key(source: str, row_number: int, row: dict) -> str:
    payload = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    # Row number is part of the key so an exact duplicate source row is preserved as
    # provenance, while the same unchanged file remains idempotent on re-run.
    return hashlib.sha256(f"{source}:{row_number}:{payload}".encode()).hexdigest()


def _find_person(conn: sqlite3.Connection, norm: dict) -> tuple[sqlite3.Row | None, str, str]:
    # Email and phone are independently strong. A disagreement is not auto-merged.
    by_email = conn.execute("SELECT * FROM persons WHERE normalized_email=?", (norm["email"],)).fetchone() if norm["email"] else None
    by_phone = conn.execute("SELECT * FROM persons WHERE normalized_phone=?", (norm["phone"],)).fetchone() if norm["phone"] else None
    if by_email and by_phone and by_email["id"] != by_phone["id"]:
        return None, "conflicting_strong_identifiers", "review"
    if by_email:
        return by_email, "normalized_email", "high"
    if by_phone:
        return by_phone, "normalized_phone", "high"
    return None, "new_person", "high"


def _upsert_person(conn: sqlite3.Connection, norm: dict, raw: dict, source: str) -> tuple[int, str, str]:
    person, rule, confidence = _find_person(conn, norm)
    if person:
        # Fill an absent strong identifier only. Never overwrite canonical values from another source.
        conn.execute("UPDATE persons SET normalized_email=COALESCE(normalized_email, ?), normalized_phone=COALESCE(normalized_phone, ?), normalized_city=COALESCE(normalized_city, ?) WHERE id=?", (norm["email"], norm["phone"], norm["city"], person["id"]))
        return person["id"], rule, confidence
    canonical = raw[SOURCE_MAP[source]["name"]].strip()
    cursor = conn.execute("INSERT INTO persons(canonical_name,normalized_email,normalized_phone,normalized_city) VALUES(?,?,?,?)", (canonical, norm["email"], norm["phone"], norm["city"]))
    return cursor.lastrowid, rule, confidence


def ingest(db_path: str | Path, input_dir: str | Path) -> dict:
    """Load all rows. Re-running is safe: source rows use a stable content key and are updated."""
    conn = connect(db_path)
    summary = {"rows": 0, "matched": 0, "new_people": 0, "invalid": 0}
    try:
        with conn:
            for source, config in SOURCE_MAP.items():
                with (Path(input_dir) / config["path"]).open(encoding="utf-8-sig", newline="") as f:
                    for row_number, row in enumerate(csv.DictReader(f), start=2):
                        summary["rows"] += 1
                        raw = {str(k): v for k, v in row.items()}
                        key, error = _source_key(source, row_number, raw), _row_error(source, row)
                        existing = conn.execute("SELECT id, person_id FROM source_records WHERE source_key=?", (key,)).fetchone()
                        if existing:
                            continue
                        cur = conn.execute("INSERT INTO source_records(source_name,source_row,source_key,raw_json,valid,ingestion_error) VALUES(?,?,?,?,?,?)", (source, row_number, key, json.dumps(raw, ensure_ascii=False), int(not error), error))
                        record_id = cur.lastrowid
                        if error:
                            summary["invalid"] += 1
                            conn.execute("INSERT INTO identity_decisions(source_record_id,person_id,match_rule,confidence,notes) VALUES(?,?,?,?,?)", (record_id, None, "not_matched_invalid_row", "none", error))
                            continue
                        norm = normalized_record(source, row)
                        person_id, rule, confidence = _upsert_person(conn, norm, row, source)
                        summary["new_people"] += rule == "new_person"
                        summary["matched"] += rule != "new_person"
                        conn.execute("UPDATE source_records SET person_id=? WHERE id=?", (person_id, record_id))
                        conn.execute("INSERT INTO identity_decisions(source_record_id,person_id,match_rule,confidence) VALUES(?,?,?,?)", (record_id, person_id, rule, confidence))
                        for field, raw_value in row.items():
                            normalized = {config["name"]: norm["name"], config["email"]: norm["email"], config["phone"]: norm["phone"], config["city"]: norm["city"], config["status"]: norm["status"], config["skills"]: ", ".join(norm["skills"])}.get(field)
                            conn.execute("INSERT INTO field_provenance(person_id,source_record_id,field_name,raw_value,normalized_value) VALUES(?,?,?,?,?)", (person_id, record_id, field, raw_value, normalized))
    finally:
        conn.close()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest ConsultBae CSV data into SQLite.")
    parser.add_argument("--db", default="data/consultbae.sqlite3")
    parser.add_argument("--input-dir", default="data/input")
    args = parser.parse_args()
    print(json.dumps(ingest(args.db, args.input_dir), indent=2))


if __name__ == "__main__":
    main()
