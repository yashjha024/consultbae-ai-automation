# Assignment self-audit

- [x] Task 1: SQLite schema, source provenance, deterministic normalizers, conservative person resolution, and rerunnable ingestion are implemented and tested.
- [ ] Task 2: n8n/Make/Zapier automation is intentionally not implemented; the brief requires a real no-code flow, which cannot be replaced by this Python backend.
- [x] Task 3 backend: `analyze_audio()` extracts WAV duration, sample rate, bitrate, and RMS loudness; non-WAV support is available when `ffprobe` is installed. The HTTP API stores an upload, links/creates a person, stores analysis results/errors, and lists submissions.
- [ ] Task 3 frontend/deployment: intentionally left for the frontend agent. The API is ready for a multipart upload form and a submissions view.
- [x] Task 4: the specific, quantified report is in `reports/data-quality.md`.
- [ ] Task 5: optional stretch write-up is left out to keep this backend assignment scoped.
