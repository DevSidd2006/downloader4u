# SaaS Architecture for Artemis Video Suite

## Executive Summary
Artemis Video Suite remains a free, local-first experience designed to orchestrate yt-dlp downloads with SaaS-inspired guardrails. There is a single implicit workspace that exposes a lightweight REST surface, while the browser owns persistence for presets, queued items, and download history via `localStorage`. The server orchestrates downloads, enforces per-download limits, and exposes telemetry so the workspace feels production-grade without requiring authentication or SQL databases.

## Architecture Overview

### System Components (Free mode)
```
┌─────────────────────────────┐
│    Browser (localStorage)   │
└─────────────┬───────────────┘
              │
      ┌───────▼────────┐
      │ Flask API +     │
      │ Async Downloader│
      └───────┬────────┘
              │
      ┌───────▼────────┐
      │ ThreadPool /    │
      │ yt-dlp workers  │
      └───────┬────────┘
              │
      ┌───────▼────────┐
      │ downloads-      │
      │ history.json    │
      └────────────────┘
```

### 1. Local-first Free Mode
- **Authentication:** none. Every request is treated as coming from the same workspace, and the browser enforces access boundaries through saved presets.
- **Client responsibilities:** store presets, queued URLs, and download history in `localStorage` or IndexedDB; cache telemetry snapshots to avoid constant polling; keep the last-used download directory and format choices.
- **Server responsibilities:** accept POST requests to queue downloads, return progress/telemetry via polling endpoints, cancel downloads, and stream generated files via pre-signed URLs (if external storage is configured) or direct file downloads when possible.
- **Safety nets:** rate limiting, input validation, sensible timeout limits, and quota enforcement keep the local server from being overwhelmed by repeated, malformed requests.

**API surface (all routes are open):**
```
POST   /api/v1/downloads           # queue one or many URLs
GET    /api/v1/downloads           # list history + progress
GET    /api/v1/downloads/:id       # download detail + signed URL
DELETE /api/v1/downloads/:id       # cancel an in-progress job
GET    /api/v1/telemetry           # queue depth, stats, averages
GET    /api/v1/configuration       # client can read default presets
```

When you later decide to host Artemis as a multi-tenant SaaS, these endpoints can be wrapped with tenant-scoped persistence and optional role checks.

### 2. Resource Quotas & Throttling
- **Per-download limits:** `yt-dlp` jobs are capped by `Config.DOWNLOAD_TIMEOUT`, `Config.MAX_FILE_SIZE`, and the thread pool size defined in `MAX_WORKERS`.
- **Queue depth cap:** the API returns HTTP 429 when too many jobs are queued or running, protecting CPU/disk.
- **Rate limiting:** if enabled, the decorator counts requests per IP and returns a `Retry-After` header when limits are reached.
- **Storage constraints:** completed downloads are stored locally, and cleanup jobs delete files older than `CLEANUP_AFTER_DAYS` to bound space usage.

### 3. Local storage representation
The entire metadata model lives in `downloads-history.json`. Each download record resembles:
```json
{
  "id": "d3a2f7d0-5a8c-4f6b-9a2b-1f8a8827c9b4",
  "url": "https://youtu.be/abc123",
  "title": "Deep Dive",
  "status": "completed",
  "format_preset": "Smart (best combined)",
  "quality": "best",
  "progress": 100,
  "file_size": 18230128,
  "storage_path": "downloads/d3a2f7d0-5a8c-4f6b-9a2b-1f8a8827c9b4.mp4",
  "metadata": {"title": "Deep Dive", "uploader": "Channel"},
  "created_at": "2026-01-04T12:00:00Z",
  "completed_at": "2026-01-04T12:00:30Z"
}
```
Only the most recent 200 entries are kept so the file size stays predictable. For a hosted upgrade you can map every field to a relational table, but for now the JSON file is the single source of truth.

### 4. Telemetry & Observability
- **Endpoints:** `/api/v1/telemetry` reports queued, running, failed, and completed counts plus average progress and worker utilization.
- **Logs:** The server logs to stdout/stderr (configurable via `LOG_LEVEL`); you can pipe these into a file, filebeat, or simple console viewer.
- **Browser dash:** The frontend polls telemetry every 3 seconds and renders a control-room view that mirrors the original single-user UI.

### 5. Security & Stability
- **Input sanitization:** All incoming payloads are validated and any unsupported fields trigger 400 responses.
- **Rate limiting:** configurable per-IP counters prevent abusive polling.
- **Transport:** configure TLS via a reverse proxy or local tunneling tool.
- **File validation:** downloads stay within configured `MAX_FILE_SIZE`, and filenames are normalized to avoid path traversal.
- **Secrets:** Environment variables (or local `.env`) store keys for optional integrations (S3, Gmail, Stripe) to keep credentials out of source control.

### 6. Scalability & Deployment (Local-first)
- **Execution model:** `flask run` or a minimal WSGI worker (Gunicorn/Uvicorn) runs the API; the downloader uses `ThreadPoolExecutor` or Celery (with Redis as broker) if you need more parallelism.
- **Storage:** Completed files land under `downloads/`; `downloads-history.json` sits at the repo root for easy backups.
- **Provisioning:** start the server via a simple script or process manager (`pm2`, `Supervisor`, `systemd`).
- **Upsizing:** If you later run Artemis on multiple hosts, add a load balancer, switch the history file to PostgreSQL, and add Redis for locking.

### 7. Next Steps
1. Keep the `downloads-history.json` synced with the frontend (every POST should append, every GET should stream the latest slice).
2. Store frontend presets in `localStorage` keyed by `workspace-presets:v1` so every browser retains its UI state.
3. When you add authentication, reuse the existing endpoints but wrap them with token decorators and migrate the JSON state to a database as described in the original multi-tenant blueprint.
4. Document how to switch to S3/Cloud Storage using `Config` flags so users can swap storage backends without code changes.

**Document Version:** 1.0  
**Last Updated:** January 4, 2026  
**Author:** Artemis Team
