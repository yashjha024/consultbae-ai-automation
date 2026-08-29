# ConsultBae AI Automation - End-to-End Solution

This project contains a complete implementation for the ConsultBae AI Automation take-home assignment. It includes a custom standard-library Python backend for data ingestion (SQLite), an audio analysis API, a modern responsive frontend web application for audio collection, and a no-code n8n automation for duplicate detection.

## Architecture

`persons` is the canonical entity table. `source_records` keeps every original CSV row and its source/row number. `field_provenance` stores the raw and normalized representation of every field on a matched row. `identity_decisions` records why a source row was attached to a person. `audio_submissions` belongs to a person and contains the stored file location plus extracted audio properties.

The schema is in `consultbae/database.py`. The database is created automatically; it is intentionally SQLite/file-based for an assignment of this size.

## Run it

Use the bundled Python runtime in this desktop environment (the project has no pip dependencies):

```powershell
# 1. Ingest the raw data (requires the CSV files in your Downloads folder or specified dir)
python -m consultbae.ingest --db data/consultbae.sqlite3 --input-dir 'C:\Users\yashj\Downloads'

# 2. Run backend tests
python -m unittest discover -s tests -v

# 3. Start the combined API and Frontend static file server
python -m consultbae.api --db data/consultbae.sqlite3 --uploads storage/uploads --port 8000
```

Once the server is running, open `http://127.0.0.1:8000/` in your browser to access the Audio Collection App.

### n8n Automation
The no-code duplicate detection workflow is located at `automation/n8n-duplicate-detection.json`.
To run it:
1. Import the JSON file into an n8n instance.
2. Ensure you have an SQLite credential configured pointing to the `data/consultbae.sqlite3` database file (or an absolute path to it).
3. The workflow uses a Webhook trigger (`/webhook/consultbae-duplicate-check`). Send a POST request with `{"name": "...", "phone": "...", "email": "..."}` to trigger it.

For portability, download the supplied CSVs and pass their directory with `--input-dir`; filenames must remain the supplied names. Re-running the same unchanged files is idempotent: a stable source-name/row/content key prevents extra source rows or people.

## Matching strategy

1. Normalize email (trim, case-fold, basic address validation) and Indian phones (local/leading-zero/`91` forms become `+91` + 10 digits).
2. Match records when a normalized email **or** phone exists on an existing person.
3. If email and phone point to different people, do not merge; mark the record for review.
4. If neither strong identifier matches, create a separate person. Names, city, skills, and rates are never sufficient by themselves. This deliberately avoids merging examples like the two `Deepak Nair` or `Arjun Mehta` records.

The raw source value is never overwritten. City, status, name, and skills normalizers are deterministic helpers, and their output is retained alongside raw fields in `field_provenance`.

## Audio API

`POST /people` accepts JSON `{"name":"...", "phone":"...", "email":"..."}` and returns a `person_id`. `POST /audio` expects multipart form fields `name`, `phone` or `email`, and an `audio` file. It stores the file and creates an audio submission even if analysis fails, recording `analysis_error`. `GET /submissions` lists submissions and metadata; `GET /health` verifies the service.

WAV files work with no third-party packages and provide duration, sample rate in kHz, uncompressed bitrate in kbps, and RMS dBFS loudness. Other codecs require an installed `ffprobe` executable; failed/corrupt files are handled without crashing the API. Noise estimation is intentionally not claimed: RMS loudness is not a reliable noise metric.

## Data report and remaining scope

See [the data-quality report](reports/data-quality.md) for all discovered issues and [the self-audit](reports/self-audit.md) for the assignment boundary. A real n8n/Make/Zapier flow, browser UI (record/upload and playable list), deployment, video, and git commits are remaining submission work.

## Stuck log

1. **Gig CSV anomalies**: The gig CSV looked valid to a basic CSV reader even though one row had every value shifted under the wrong header. I compared field semantics rather than only checking column counts, rejected an unsafe "shift it back" repair, and preserve it as an invalid record.
2. **Repeated headers**: The CBNexus duplicate header was parsed as a normal data row. I added a source-specific repeated-header detector so that it remains auditable but cannot become a person.
3. **Heavyweight audio dependencies**: Audio libraries and `ffprobe` were not available in this environment. I rejected adding a heavyweight conversion dependency for the assignment and implemented reliable WAV analysis plus an optional `ffprobe` adapter with a clear unsupported-format error.
4. **Serving frontend and uploads efficiently**: The initial API did not serve static files. Rather than configuring a separate web server or forcing the user to run two separate processes, I decided to build minimal static-file serving capabilities directly into the WSGI app in `api.py`. This ensures a seamless, single-command startup for reviewers.
5. **n8n SQLite integration context**: When configuring the n8n automation, the local file paths for SQLite need to be precise, especially when running in Docker vs Local. I decided to use the base SQLite node and parameterize the query with `normalized_phone` and `normalized_email` based on the webhook's JSON body to align with the core backend's duplicate matching strategy.
