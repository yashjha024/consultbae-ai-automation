# Task 5 — Scaling to 5,000 Workers Over a Single Weekend

## Executive Summary
Launching the audio collection app to 5,000 gig workers over a 48-hour weekend translates to a high-concurrency burst workload. If 5,000 workers submit 1–3 audio recordings each (~10,000 total submissions), the average traffic over 48 hours would be modest, but the system must handle bursts when large groups submit simultaneously. 

---

## 1. What Breaks First?

1. **Synchronous Single-Process WSGI & Audio Analysis (Immediate Bottleneck)**:
   - **Failure Mode**: The current server processes audio uploads synchronously in-thread using Python's `wsgiref.simple_server`. When workers upload large WAV files (e.g., 10MB–50MB), server threads block on multipart parsing, disk I/O, and CPU-bound RMS loudness calculations.
   - **Impact**: Request queues fill up within seconds, resulting in HTTP 504 Gateway Timeouts and dropped client connections.

2. **SQLite Database Locking (`database is locked` / WinError)**:
   - **Failure Mode**: SQLite only supports a single writer at a time. Concurrent transactions attempting to insert `persons` and `audio_submissions` simultaneously will exhaust the default timeout and throw `sqlite3.OperationalError: database is locked`.

3. **Local Filesystem & Disk Space Exhaustion**:
   - **Failure Mode**: Storing uncompressed 16-bit 44.1kHz WAV files locally on a single instance consumes ~5MB per minute of audio. At roughly 1–3 minutes per submission, uncompressed 16-bit 44.1kHz WAV files would consume approximately 5–15 MB per submission, or ~50–150 GB for 10,000 submissions. A single server running low on IOPS or disk space will crash the application and corrupt local storage.

4. **Network Upload Failures & Mobile Retries**:
   - **Failure Mode**: Gig workers on unreliable mobile 3G/4G networks will suffer frequent connection drops during large uploads. Without chunked/resumable upload mechanisms, users will repeatedly re-record or re-upload, multiplying the load on the backend.

---

## 2. Pre-Launch Architecture Changes

### A. Storage & Presigned Direct Uploads (Zero-Server Load)
- **Eliminate server-routed file streams**: Client requests a short-lived presigned upload URL from an API endpoint (`POST /submissions/presign`).
- **Direct S3 / Cloudflare R2 Upload**: The browser uploads audio directly to object storage (e.g., AWS S3 or Cloudflare R2) via HTTP `PUT`. Cloudflare R2 eliminates egress bandwidth fees.
- **Client-Side Compression**: Use browser Web Audio API to record/encode to lightweight Opus/WebM or compressed AAC (~32–64 kbps) instead of uncompressed PCM WAV (~1,411 kbps), reducing payload sizes by **95%** (from 15MB down to 700KB per minute).

### B. Asynchronous Event-Driven Pipeline
- **Decouple API from Processing**: Once S3 receives the file, an S3 Event Notification or webhook triggers a lightweight worker (AWS Lambda or Celery/Redis worker).
- **Background Audio Analysis**: Metadata extraction (duration, sample rate, bitrate, loudness, noise floor) runs asynchronously without blocking user-facing APIs.
- **Worker Auto-scaling**: Serverless workers can scale horizontally based on queue depth and concurrency, subject to configured provider limits.

### C. Database Architecture
- **Managed PostgreSQL (e.g., AWS RDS / Supabase / Neon)** with connection pooling (PgBouncer) replacing single-file SQLite.
- **Row-level concurrency** and indexed identity matching on `(normalized_phone, normalized_email)` ensure sub-5ms lookup latency under high write throughput.

---

## 3. Duplicate Prevention & Resilience

- **Idempotency Keys & Session Tokens**: The frontend generates a unique UUID per recording attempt. If a user double-clicks or retries an upload, the backend deduplicates by the idempotency key.
- **Atomic Upserts**: Use database-level `INSERT ... ON CONFLICT (normalized_phone) DO UPDATE` or database transactions to prevent duplicate `persons` records from race conditions.
- **Redis Rate Limiting**: Limit submission requests to 5 attempts per IP/device per minute to prevent accidental flood traffic or automated script abuse.

---

## 4. Cost Breakdown (5,000 Workers, 10,000 Submissions)

| Component | Architecture Choice | Estimated Weekend Cost |
|---|---|---|
| **Storage (Object Storage)** | Cloudflare R2 / AWS S3 (~10 GB compressed audio (assuming 10,000 × ~2-minute recordings at ~64 kbps)) | **$0.15** |
| **Data Egress / Bandwidth** | Cloudflare R2 (Free egress) / S3 with CloudFront | **$0.00 – $0.90** |
| **Compute & API** | 1x Cloud Container (Render/Fly.io) or AWS Lambda | **$2.00 – $5.00** |
| **Database** | Managed Postgres (Neon / Supabase Free/Pro tier) | **$0.00 – $10.00** |
| **Total Estimated Cost** | High-availability, zero-downtime stack | **< $20.00** |
