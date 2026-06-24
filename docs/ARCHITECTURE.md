# Architecture

## Principles

1. **Explainability first.** Every score is reconstructable from timestamped,
   per-modality evidence. No black boxes.
2. **Parallelism.** The three expensive modality analyses run concurrently.
3. **Service-orientation + DI.** Each stage is a `Protocol`; concrete providers
   are wired only in `orchestration/container.py`.
4. **Framework-agnostic core.** `domain/`, `services/`, `orchestration/` import
   neither FastAPI nor Celery. The web and worker layers are thin adapters.
5. **Auditability.** Every artifact (frames, OCR, transcript, visual, graph,
   timeline, verdict, report) is persisted, plus an `audit_log` of stage events.

## Layered view

```
┌──────────────────────────────────────────────────────────────┐
│ Adapters                                                       │
│   api/  (FastAPI)            workers/  (Celery)                │
│      │  validate+enqueue        │  persist + progress + webhook│
└──────┼──────────────────────────┼─────────────────────────────┘
       ▼                          ▼
┌──────────────────────────────────────────────────────────────┐
│ orchestration/  AnalysisOrchestrator  +  EngineContainer (DI) │
└──────┬───────────────────────────────────────────────────────┘
       ▼
┌──────────────────────────────────────────────────────────────┐
│ services/  (ports = interfaces.py, adapters = impls + mocks)   │
│   ingestion · scene · frame/audio · ocr · speech · visual      │
│   text_risk · fusion · timeline · reasoning · reporting        │
└──────┬───────────────────────────────────────────────────────┘
       ▼
┌──────────────────────────────────────────────────────────────┐
│ domain/  enums · value objects (Pydantic) · API schemas        │
└──────────────────────────────────────────────────────────────┘
       ▲
┌──────┴───────────────────────────────────────────────────────┐
│ db/  engine · ORM models · repositories (the only ORM caller)  │
└──────────────────────────────────────────────────────────────┘
```

## The pipeline (Steps 1–10)

| Step | Service | Output | Parallel? |
|------|---------|--------|-----------|
| 1 Ingestion | `OpenCVIngestionService` | `VideoMetadata` | — |
| 2 Scene detect | `PySceneDetectDetector` | `list[Scene]` | — |
| 3 Frames + audio | `OpenCVFrameExtractor`, `FFmpegAudioExtractor` | `list[Frame]`, audio.wav | — |
| 4 OCR | `OcrProvider` (Paddle/mock) | `list[OcrResult]` | ✅ |
| 5 Speech | `SpeechProvider` (Whisper/mock) | `Transcript` | ✅ |
| 6 Visual | `VisualProvider` (Qwen-VL/mock) | `list[VisualDetection]` | ✅ |
| 7 Text risk | `TextRiskAnalyzer` | `list[TextRiskEvidence]` | — |
| 8 Fusion | `FusionService` | `EvidenceGraph` | — |
| 9 Timeline | `TimelineService` | timeline + player markers | — |
| 10 Judge | `ReasoningEngine` (OpenRouter, 1×) | `JudgeVerdict` | — |
| — Report | `ReportingService` | `AnalysisReport` | — |

Steps 4–6 are dispatched with `asyncio.gather` inside
`AnalysisOrchestrator.analyze_modalities`.

## Why the 72B model is called once

Per-frame VLM/LLM calls are expensive and slow. Instead:
- Cheap/medium models (PaddleOCR, Whisper, Qwen-VL-7B) extract raw signals.
- The deterministic `TextRiskAnalyzer` + `FusionService` distil those into a
  compact evidence package.
- The 72B judge receives the **pre-digested package** and renders one verdict.

This bounds cost to `O(1)` 72B calls per video and keeps latency predictable.

## Fusion & evidence graph

`FusionService` normalises OCR/speech text-risk and visual detections into a
single `EvidenceRef` stream, clusters temporally-close same-category evidence
into cross-modal `FusedEvent`s (confidence via **noisy-OR** + corroboration
bonus), and links co-occurring different-category events into an adjacency map —
the unified evidence graph.

## Resilience

- **OCR/speech/visual**: missing GPU libs → graceful degradation / placeholders.
- **Judge**: retries (exp. backoff) → JSON repair → one regeneration → schema
  validation → deterministic fallback verdict (`fallback_used=true`).
- **Webhooks**: signed (HMAC-SHA256), retried; never fail the job.

## Scaling / Kubernetes-readiness

- API and workers are separate, stateless, horizontally-scalable processes.
- Redis is the broker; Postgres is the system of record; media on a shared
  volume / object store (`AIMW_STORAGE_DIR`).
- Workers use `prefetch_multiplier=1` + `acks_late` so heavy tasks are processed
  one-at-a-time and re-queued on crash.
- Provider mix is env-driven, so GPU worker pools (real providers) and CPU pools
  can coexist behind the same queue.

## Integration surface

The core engine (`AnalysisOrchestrator`) is import-and-call. Build SDKs (Python/
TS/Go) over the REST contract in [`API_CONTRACTS.md`](API_CONTRACTS.md). Webhooks
push completed reports to government-monitoring / compliance / moderation
systems, Telegram bots, dashboards, or external SaaS.
