# Database Schema (PostgreSQL)

Canonical definition lives in `src/aimw/db/models.py` (SQLAlchemy 2.0). Create
with `python -m aimw.scripts.init_db` (or Alembic in production). Structured
artifacts are stored as `JSONB` for full fidelity/auditability, with key scalars
promoted to indexed columns for querying.

## Entity overview

```
videos 1──* jobs
videos 1──* scenes
videos 1──* frames
videos 1──* ocr_results
videos 1──1 transcripts
videos 1──* visual_detections
videos 1──1 evidence_graphs
videos 1──1 timelines
videos 1──1 reports
audit_log  (video_id / job_id soft references)
```

## Tables

### videos
| column | type | notes |
|--------|------|-------|
| video_id (PK) | varchar(64) | `vid_…` |
| filename | varchar(512) | |
| source_platform | varchar(64) | upload / tiktok / instagram / … |
| source_url | text | nullable |
| duration_seconds | float | |
| fps | float | |
| width, height | int | |
| size_bytes | int | |
| container | varchar(16) | mp4/mov/webm |
| storage_path | text | local/object-store key |
| uploaded_at | timestamptz | |
| meta | jsonb | full `VideoMetadata` |

### jobs
| column | type | notes |
|--------|------|-------|
| job_id (PK) | varchar(64) | `job_…` |
| video_id (FK→videos) | varchar(64) | indexed |
| status | varchar(32) | indexed; see `JobStatus` |
| progress | int | 0–100 |
| stage_detail | text | nullable |
| error | text | nullable |
| webhook_url | text | nullable |
| created_at / updated_at / completed_at | timestamptz | |

`JobStatus`: `queued → ingesting → extracting → analyzing → fusing → judging →
reporting → completed` (or `failed`).

### scenes
`id (PK)`, `video_id (FK)`, `scene_id int`, `start float`, `end float`.

### frames
`frame_id (PK)`, `video_id (FK)`, `timestamp float (idx)`, `path text`,
`is_keyframe bool`, `scene_id int?`.

### ocr_results
`id (PK)`, `video_id (FK)`, `timestamp float`, `text`, `confidence float`,
`frame_id?`, `raw jsonb`. Composite index `(video_id, timestamp)` → searchable
OCR index.

### transcripts (1 per video)
`id (PK)`, `video_id (FK, unique)`, `language`, `full_text`, `segments jsonb`
(each with `start/end/text/confidence/words[]`).

### visual_detections
`id (PK)`, `video_id (FK)`, `timestamp float`, `frame_id?`, `scores jsonb`
(label→0..1), `evidence jsonb` (string[]).

### evidence_graphs (1 per video)
`id (PK)`, `video_id (FK, unique)`, `events jsonb` (`FusedEvent[]`),
`adjacency jsonb` (`event_id → event_id[]`).

### timelines (1 per video)
`id (PK)`, `video_id (FK, unique)`, `events jsonb` (`TimelineEvent[]`),
`markers jsonb` (`EvidencePlayerMarker[]`).

### reports (1 per video)
`id (PK)`, `video_id (FK, unique)`, `risk_score int (idx)`,
`category varchar(48) (idx)`, `confidence float`, `summary text`,
`report jsonb` (full `AnalysisReport`), `fallback_used bool`, `generated_at`.

### audit_log (append-only)
`id (PK)`, `video_id? (idx)`, `job_id? (idx)`, `stage varchar(48)`,
`message text`, `payload jsonb`, `created_at`. One row per stage transition /
error → complete audit trail.

## Retention & audit notes
- Reports/transcripts/graphs are 1-per-video and re-written on re-analysis;
  prior versions can be retained by switching `_save_*` from delete+insert to
  versioned inserts (a `version` column) if immutable history is required.
- `audit_log` is append-only and should be retained per your compliance policy.
