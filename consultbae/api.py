"""Small stdlib HTTP API for the future audio web app.

Run with: python -m consultbae.api --db data/consultbae.sqlite3
"""
from __future__ import annotations

import argparse
import cgi
import json
import shutil
import uuid
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from .audio import AudioAnalysisError, analyze_audio
from .database import connect
from .normalization import normalize_email, normalize_name, normalize_phone


def _json(start_response, status: str, payload: object):
    body = json.dumps(payload, default=str).encode()
    start_response(status, [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
    return [body]


def _person(conn, name: str | None, phone: str | None, email: str | None):
    phone, email = normalize_phone(phone), normalize_email(email)
    existing = conn.execute("SELECT * FROM persons WHERE normalized_phone=? OR normalized_email=? ORDER BY id LIMIT 1", (phone, email)).fetchone()
    if existing:
        return existing["id"]
    normalized_name = normalize_name(name)
    if not normalized_name or not (phone or email):
        raise ValueError("name and at least one valid email or Indian phone number are required")
    return conn.execute("INSERT INTO persons(canonical_name,normalized_email,normalized_phone) VALUES(?,?,?)", (name.strip(), email, phone)).lastrowid


def app(db_path: str | Path, upload_dir: str | Path):
    db_path, upload_dir = Path(db_path), Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    def application(environ, start_response):
        conn = connect(db_path)
        try:
            method, path = environ["REQUEST_METHOD"], environ["PATH_INFO"]
            if method == "GET" and path == "/health":
                return _json(start_response, "200 OK", {"ok": True})
            if method == "GET" and path == "/submissions":
                rows = [dict(x) for x in conn.execute("SELECT a.*, p.canonical_name FROM audio_submissions a JOIN persons p ON p.id=a.person_id ORDER BY a.id DESC")]
                return _json(start_response, "200 OK", rows)
            if method == "POST" and path == "/people":
                payload = json.loads(environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH") or 0)) or b"{}")
                with conn:
                    person_id = _person(conn, payload.get("name"), payload.get("phone"), payload.get("email"))
                return _json(start_response, "201 Created", {"person_id": person_id})
            if method == "POST" and path == "/audio":
                form = cgi.FieldStorage(fp=environ["wsgi.input"], environ=environ, keep_blank_values=True)
                uploaded = form["audio"] if "audio" in form else None
                if not uploaded or not getattr(uploaded, "file", None) or not uploaded.filename:
                    return _json(start_response, "400 Bad Request", {"error": "multipart field 'audio' is required"})
                suffix = Path(uploaded.filename).suffix.casefold()
                stored = upload_dir / f"{uuid.uuid4().hex}{suffix}"
                with stored.open("wb") as f:
                    shutil.copyfileobj(uploaded.file, f)
                try:
                    metadata, error = analyze_audio(stored), None
                except AudioAnalysisError as exc:
                    metadata, error = {}, str(exc)
                try:
                    with conn:
                        person_id = _person(conn, form.getfirst("name"), form.getfirst("phone"), form.getfirst("email"))
                        cur = conn.execute("INSERT INTO audio_submissions(person_id,original_filename,stored_path,duration_seconds,sample_rate_khz,bitrate_kbps,loudness_dbfs,audio_format,analyzer,analysis_error) VALUES(?,?,?,?,?,?,?,?,?,?)", (person_id, uploaded.filename, str(stored), metadata.get("duration_seconds"), metadata.get("sample_rate_khz"), metadata.get("bitrate_kbps"), metadata.get("loudness_dbfs"), metadata.get("format"), metadata.get("analyzer"), error))
                    return _json(start_response, "201 Created", {"submission_id": cur.lastrowid, "metadata": metadata, "analysis_error": error})
                except Exception:
                    stored.unlink(missing_ok=True)
                    raise
            return _json(start_response, "404 Not Found", {"error": "not found"})
        except (ValueError, json.JSONDecodeError) as exc:
            return _json(start_response, "400 Bad Request", {"error": str(exc)})
        finally:
            conn.close()
    return application


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/consultbae.sqlite3")
    parser.add_argument("--uploads", default="storage/uploads")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"Listening on http://127.0.0.1:{args.port}")
    make_server("127.0.0.1", args.port, app(args.db, args.uploads)).serve_forever()


if __name__ == "__main__":
    main()
