# API Contracts (v1)

Base prefix: `/api/v1` (configurable via `AIMW_API_PREFIX`). Interactive docs at
`/docs` (Swagger) and `/redoc`. Every response carries an `X-Request-ID` header.

`{identifier}` accepts either a `job_id` or a `video_id` (resolved transparently)
for all result endpoints.

---

## POST /api/v1/analyze
Submit a video. `multipart/form-data`:

| field | type | required | notes |
|-------|------|----------|-------|
| file | file | one of file/source_url | mp4/mov/webm |
| source_url | string | one of file/source_url | direct media URL (platform scraping = integration point) |
| source_platform | string | no | `upload` (default), `tiktok`, … |
| webhook_url | string | no | POSTed the final report on completion |

**202 Accepted**
```json
{
  "job_id": "job_3f…",
  "video_id": "vid_9a…",
  "status": "queued",
  "poll_url": "/api/v1/status/job_3f…",
  "created_at": "2026-06-24T10:00:00Z"
}
```
Errors: `400` (neither file nor url), `413` (too large), `415` (bad extension).

---

## GET /api/v1/status/{job_id}
```json
{
  "job_id": "job_3f…", "video_id": "vid_9a…",
  "status": "judging", "progress": 80,
  "stage_detail": "final compliance reasoning",
  "error": null,
  "created_at": "…", "updated_at": "…", "completed_at": null
}
```
`404` if unknown job.

---

## GET /api/v1/report/{identifier}  ·  GET /api/v1/analysis/{identifier}
Full, explainable report (the OUTPUT FORMAT contract):

```json
{
  "video_id": "vid_9a…",
  "report": {
    "video_id": "vid_9a…",
    "risk_score": 92,
    "category": "illegal_gambling",
    "confidence": 0.95,
    "summary": "The video promotes an online casino and encourages deposits using bonus incentives.",
    "explanation": "…grounded in the evidence…",
    "timeline": [
      {"start": 32.5, "end": 38.2, "severity": "high",
       "category": "illegal_gambling", "confidence": 0.94,
       "evidence": ["roulette interface", "bonus banner"],
       "sources": ["ocr", "visual"]}
    ],
    "player_markers": [
      {"timestamp": 32.5, "label": "Illegal gambling detected",
       "severity": "high", "icon": "🔴", "display_time": "00:32"}
    ],
    "evidence": {"visual": [], "audio": [], "ocr": []},
    "metadata": { "...": "VideoMetadata" },
    "fallback_used": false,
    "generated_at": "…"
  },
  "metadata": { "...": "VideoMetadata" }
}
```
`/analysis/{identifier}` wraps the same report with job status:
`{ "job_id": "...", "status": "completed", "report": { … } }`.

---

## GET /api/v1/timeline/{identifier}
Drives the Evidence Player (frontend jumps to timestamps):
```json
{
  "video_id": "vid_9a…",
  "events": [ { "...": "TimelineEvent" } ],
  "player_markers": [
    {"timestamp": 32, "label": "Roulette detected", "severity": "high",
     "icon": "🔴", "display_time": "00:32"},
    {"timestamp": 51, "label": "Guaranteed income claim", "severity": "medium",
     "icon": "🟠", "display_time": "00:51"}
  ]
}
```

## GET /api/v1/evidence/{identifier}
```json
{ "video_id": "vid_9a…",
  "evidence": { "visual": [ "...VisualDetection" ],
                "audio":  [ "...TextRiskEvidence(speech)" ],
                "ocr":    [ "...TextRiskEvidence(ocr)" ] } }
```

## GET /api/v1/risk/{identifier}
```json
{ "video_id": "vid_9a…", "risk_score": 92, "category": "illegal_gambling",
  "confidence": 0.95, "summary": "…", "fallback_used": false }
```

## GET /health
```json
{ "status": "ok", "version": "0.1.0", "env": "production",
  "checks": {"database": "ok", "redis": "ok",
             "ocr_provider": "real", "speech_provider": "real",
             "visual_provider": "real",
             "reasoning_model": "qwen/qwen-2.5-72b-instruct"} }
```

---

## Webhooks
On completion/failure the platform `POST`s to `webhook_url`:
```json
{ "job_id": "job_3f…", "status": "completed", "report": { … } }
```
Headers: `X-AIMW-Signature: sha256=<hmac>` over the raw body, keyed by
`AIMW_WEBHOOK_SIGNING_SECRET`. Verify before trusting. Delivery is retried with
exponential backoff; failures never fail the analysis job.

## Risk categories
`illegal_gambling`, `casino_advertising`, `sports_betting`, `pyramid_scheme`,
`ponzi_scheme`, `guaranteed_income`, `referral_scam`, `fake_investment`,
`financial_manipulation`, `hidden_advertising`, `suspicious_financial`, `none`.

## Error envelope
```json
{ "error": "validation_error", "detail": "…", "request_id": "…" }
```
