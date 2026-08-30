# Assignment self-audit

- [x] Task 1: SQLite schema, source provenance, deterministic normalizers, conservative person resolution, and rerunnable ingestion are implemented and tested.
- [x] Task 2: An importable n8n duplicate-detection workflow is exported to `automation/n8n-duplicate-detection.json`. It requires a locally configured SQLite credential; alert delivery additionally requires `CONSULTBAE_DUPLICATE_ALERT_URL`.
- [x] Task 3 backend: `analyze_audio()` extracts WAV duration, sample rate, bitrate, and RMS loudness. The HTTP API stores uploads, links/creates people, and stores analysis results/errors.
- [x] Task 3 frontend: A responsive single-page application is implemented in `frontend/`, providing WAV file upload and Web Audio API in-browser recording (encoded to WAV), plus a listing view with an HTML5 `<audio>` player.
- [x] Task 4: The specific, quantified report is in `reports/data-quality.md`.
- [ ] Task 5: Optional stretch write-up is left out to keep this assignment scoped.
