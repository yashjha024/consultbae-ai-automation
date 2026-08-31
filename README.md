# ConsultBae AI Automation - End-to-End Solution

This project contains a complete implementation for the ConsultBae AI Automation take-home assignment. It includes a custom standard-library Python backend for data ingestion (SQLite), an audio analysis API, a modern responsive frontend web application for audio collection, and a no-code n8n automation for duplicate detection.

## Architecture

`persons` is the canonical entity table. `source_records` keeps every original CSV row and its source/row number. `field_provenance` stores the raw and normalized representation of every field on a matched row. `identity_decisions` records why a source row was attached to a person. `audio_submissions` belongs to a person and contains the stored file location plus extracted audio properties.

The schema is in `consultbae/database.py`. The database is created automatically; it is intentionally SQLite/file-based for an assignment of this size.

## Run it

Python 3.12+ is required; the project has no pip dependencies. The supplied CSV fixtures are committed in `data/input/`, so a fresh clone runs without machine-specific paths:

```powershell
# 1. Ingest the committed source fixtures
python -m consultbae.ingest --db data/consultbae.sqlite3 --input-dir data/input

# 2. Run backend tests
python -m unittest discover -s tests -v

# 3. Start the combined API and Frontend static file server
python -m consultbae.api --db data/consultbae.sqlite3 --uploads storage/uploads --port 8000
```

Once the server is running, open `http://127.0.0.1:8000/` in your browser to access the Audio Collection App.

### n8n Automation

The no-code duplicate detection workflow is located at
`automation/n8n-duplicate-detection.json`.

To run it:

1. Import the JSON file into an n8n instance.
2. Start the ConsultBae Python API so that the workflow can call
   the existing `/people` endpoint.
3. Activate/publish the workflow.
4. Configure `CONSULTBAE_DUPLICATE_ALERT_URL` if a real external
   duplicate notification endpoint is desired.
5. Send a POST request to:
   `/webhook/consultbae-duplicate-check`

Example payload:

```json
{
  "name": "Candidate Name",
  "phone": "+919000000001",
  "email": "candidate@example.com"
}

```

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

See [the data-quality report](reports/data-quality.md) for all discovered issues [the Task 5 scaling analysis](reports/scale-stretch.md) for the 5,000-worker stretch scenario.

## Stuck log

### 1. Identifying a malformed row in the Gig CSV

The Gig CSV parsed successfully as a CSV, but one physical row had values
shifted into the wrong columns. A basic CSV parser therefore gave no error.

I first inspected the row against the expected field semantics rather than
assuming that successful CSV parsing meant the row was valid. I used AI to
help reason about whether the row could be safely reconstructed from the
surrounding columns.

I considered automatically shifting the values back into their expected
columns, but rejected that approach because it would require assumptions
about which value belonged to which field. A wrong repair would silently
create a false person or incorrect contact information.

Instead, I preserved the raw row for provenance, marked it invalid, and
excluded it from entity matching.

I also found a completely blank Gig row and treated it the same way:
auditable, but not eligible to create or match a person.

The final ingestion result confirmed the behavior: 105 physical rows,
3 invalid rows, 42 strong-identifier matches, and 60 canonical people.

### 2. Browser recording produced an invalid WAV

The browser microphone recording appeared to work, but the recorded preview
showed `0:00 / 0:00`. When the recording was submitted, the backend reported
that the file did not start with a valid RIFF header.

This initially looked like a microphone or MediaRecorder problem. I used AI
to help trace the complete path from microphone capture → recorded chunks →
WAV encoding → Blob/File → browser preview → backend analysis. I also
searched the RIFF/WAVE structure and JavaScript `DataView` byte ordering.

The key clue was that a separately uploaded known-good WAV worked correctly,
while the browser-generated file did not. That isolated the problem to the
WAV construction rather than microphone capture.

I considered adding a heavyweight audio dependency or using another
conversion tool, but rejected that because the assignment only required a
small working application and the project could handle PCM WAV directly.

The actual issue was incorrect construction of the WAV header. I rewrote
the encoder to generate a standards-compliant RIFF/WAVE PCM header and
correctly calculate the chunk sizes and byte fields.

I then validated the generated file independently using Python's standard
`wave` module. A synthetic recording produced a valid WAV with non-zero
duration, 44.1 kHz sampling, 16-bit PCM and 1 channel. I then verified the
real browser recording path before continuing with the submission flow.

### 3. n8n workflow compatibility and webhook debugging

The first n8n workflow used a database node that was not recognized by the
installed n8n environment. The workflow displayed an unresolved node and
could not execute.

I used the n8n error output and AI-assisted debugging to determine whether
the issue was the workflow logic or the node/runtime itself. I rejected
installing a custom database integration just to make the original design
work, because it would make the workflow more dependent on a specific n8n
environment.

I instead changed the automation to use n8n's standard HTTP Request node to
call the existing ConsultBae API, keeping SQLite owned by the Python
backend while n8n remains responsible for orchestration and duplicate
detection.

The next issue was webhook behavior. I initially tested the temporary
`/webhook-test/` endpoint while the frontend was using the production
`/webhook/` endpoint. I traced the difference and switched the application
to the production webhook for the real workflow.

I also encountered an `Unused Respond to Webhook node found in the workflow`
error. I simplified the response design so both branches converge into a
single `Respond to Webhook` node.

Finally, I tested both paths against the live n8n workflow:

- New candidate → `duplicate: false`
- Existing candidate → `duplicate: true`

Both returned HTTP 200 and completed successfully.
