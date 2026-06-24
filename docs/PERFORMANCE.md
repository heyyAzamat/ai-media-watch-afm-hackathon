# Performance & Tuning

Measured on a 12.5s, 768×1024 clip, CPU only (Apple Silicon), mock-free run.

## Where time actually goes (baseline, before tuning)

| Stage | Time | Note |
|-------|------|------|
| OCR (PaddleOCR, 16 frames) | ~59s | **dominant** — same overlay OCR'd 16× |
| Scene detect + frame extract | ~35s | OpenCV per-timestamp seeking is slow |
| 72B judge (1 call) | ~11s | once per video |
| Whisper (small) | ~11s | **not** the bottleneck |
| Qwen-VL (3 keyframes, concurrent) | ~9s | runs under `asyncio.gather` |

Takeaway: **OCR and frame handling dominate; speech does not.** Shrinking
Whisper alone barely moves the total.

## Optimizations implemented (accuracy-preserving)

1. **Frame dedup before OCR** (`ocr_frame_strategy=dedup`, default).
   On-screen text changes at scene granularity, not per second. A difference
   hash (dHash) collapses near-identical frames so OCR runs once per distinct
   overlay. Frames that can't be hashed are always kept (never drop data).
   *Measured: OCR 42.3s → 3.8s (~11×) on the test clip, 0 text lost.*
   - `keyframes` — OCR scene keyframes only (fastest, slight recall risk).
   - `all` — OCR every sampled frame (most thorough, slowest).

2. **Single-pass ffmpeg frame extraction** (replaces per-timestamp OpenCV seeks).
   *Measured: extraction ~35s → ~3s (~10×).* Falls back to OpenCV, then to
   logical placeholders, if ffmpeg is unavailable.

3. **Whisper speed knobs**: `beam_size=1` (greedy, ~2-3× vs beam=5), batched
   inference pipeline (`whisper_batched=true`, ~4× on long audio), VAD to skip
   silence, and `distil-large-v3` support (~6× faster than large-v3, near-equal
   accuracy — set `AIMW_WHISPER_MODEL=distil-large-v3`).

4. **Lighter PaddleOCR mobile models + no document preprocessing** (default).
   `PP-OCRv5_mobile_det`/`PP-OCRv5_mobile_rec` instead of the heavier PP-OCRv6
   *medium* defaults, and disabling doc-orientation / unwarping (UVDoc) /
   textline-orientation models that target scanned documents, not upright video
   overlays. Falls back to bundled defaults, then the 2.x constructor, if a
   model name is unavailable.
   *Measured: per-frame inference ~3.7s → 1.3s (~3×), identical text.*

5. **Batched OCR inference** (`ocr_device`, `ocr_batch_size`). Frames are sent
   `batch_size` at a time in a single `predict()` call (which also batches the
   recognition crops via `text_recognition_batch_size`) instead of one call per
   frame. Results are aligned back to frames; a failed/misaligned batch falls
   back to per-frame parsing so no frame is dropped. Set `AIMW_OCR_DEVICE=gpu`
   to batch crops on-device.
   *Measured (CPU, 13 frames): 42.3s → 18.9s (~2.2×) with mobile + batching;
   GPU batching yields far more. Engine init stays one-per-worker.*

6. **VLM stage-gating** (`visual_gating`). The VLM is a paid per-keyframe remote
   call, so we don't analyze every keyframe:
   - `dedup` (default) — analyze only visually-distinct keyframes. No recall
     loss, and visual stays parallel with OCR + speech.
   - `text_risk` — additionally require an OCR/speech risk hit within
     `visual_gating_window_seconds` of the keyframe. Maximum savings, but runs
     visual *after* OCR+speech. **Recall-safe by design**: it never prunes when
     text is silent and never prunes to zero, so a silent visual-only gambling
     clip is still fully analyzed.
   - `visual_max_keyframes` caps total VLM calls regardless of strategy.
   *Effect: on the test clip 3 keyframes → 1 distinct → 1 VLM call (was 3).*

7. **Skip the judge on empty evidence** (`reasoning_skip_when_empty`, default on).
   When fusion yields zero events, the 72B judge is not called at all — we return
   the definitive empty verdict (score 0, `none`, `llm_called=false`). Saves the
   ~10s + paid call on benign videos and makes the honest no-data path explicit:
   the system never fabricates analysis for a video that produced no signals.

8. **Faster judge cascade** (`reasoning_fast_model`, `reasoning_escalation`,
   **on by default**). Two ways to use a faster judge:
   - *Cascade* (default, `reasoning_escalation=true`): run the fast 32B first and
     only escalate to the authoritative 72B when the fast judge is uncertain
     (confidence below `reasoning_escalation_confidence`, or it returned the
     catch-all category). Clear-cut videos finish on the cheap model; ambiguous
     ones still get the 72B — speed on the bulk without losing accuracy on the
     hard cases.
   - *Direct* (`reasoning_escalation=false`): point `reasoning_model` at
     `qwen/qwen3-32b` for pure speed, or leave it on the 72B for max accuracy.

Net effect: full run ~105s → ~20s (~5×) on CPU, with OCR off the critical path
(per-frame OCR ~3.7s → 1.3s, only deduped frames are OCR'd, and those are
batched). On GPU the OCR/speech/VLM stages drop another order of magnitude.

## Recommended profiles

**CPU / cost-sensitive (good default):**
```
AIMW_OCR_FRAME_STRATEGY=dedup
AIMW_OCR_DET_MODEL_NAME=PP-OCRv5_mobile_det
AIMW_OCR_REC_MODEL_NAME=PP-OCRv5_mobile_rec
AIMW_OCR_USE_DOC_PREPROCESSING=false
AIMW_WHISPER_MODEL=small         # or distil-large-v3
AIMW_WHISPER_COMPUTE_TYPE=int8
AIMW_WHISPER_BEAM_SIZE=1
AIMW_FRAMES_PER_SECOND=1.0
```

**GPU / accuracy-first (production):**
```
AIMW_WHISPER_MODEL=large-v3
AIMW_WHISPER_DEVICE=cuda
AIMW_WHISPER_COMPUTE_TYPE=float16
AIMW_OCR_FRAME_STRATEGY=dedup    # still worth it — fewer VLM/OCR ops
AIMW_OCR_DEVICE=gpu              # batches recognition crops on-device
AIMW_OCR_BATCH_SIZE=16          # raise on GPU for more throughput
```
On GPU, PaddleOCR + Whisper run 10-50× faster; CPU is the real reason the
baseline is slow.

**Sovereign CPU profile (no external AI APIs, data stays on-box):**
For governmental / data-residency deployments where citizen data must not reach a
third-party AI vendor, and with no GPU to self-host a 72B model. Everything below
runs locally on CPU:
```
AIMW_OCR_PROVIDER=real        # PaddleOCR, local
AIMW_SPEECH_PROVIDER=real     # faster-whisper, local
AIMW_VISUAL_PROVIDER=none     # no VLM (emits no detections; never fabricates)
AIMW_SEMANTIC_PROVIDER=local  # local embeddings catch paraphrased scams
AIMW_OPENROUTER_API_KEY=sk-or-changeme   # placeholder ⇒ no OpenRouter call
AIMW_WHISPER_MODEL=small      # large-v3 is slow on CPU
```
With the placeholder key, `build_reasoning_engine()` returns the deterministic
on-box `FallbackReasoningEngine`, so **no request ever leaves the machine**. The
analysis then rests on local OCR + Whisper text, scored by the lexicon **and** the
local semantic matcher — the semantic layer is what recovers the nuance otherwise
lost without the LLM judge. The fallback verdict is derived from the same evidence
graph the semantic layer enriches. Verify isolation by running with outbound
network blocked. When GPU infra becomes available, point `AIMW_VISUAL_PROVIDER`
and the reasoning base URL at a self-hosted, OpenAI-compatible server (vLLM/Ollama)
to add visual + LLM nuance while still keeping data in your boundary.

9. **Environment hygiene — single ffmpeg/opencv stack** (done). Shipping both
   `opencv-python` and `PyAV` makes their bundled ffmpeg dylibs collide (the
   `libavdevice` duplicate warning) and can slow decode. The base/runtime image
   pins **`opencv-python-headless` only** and has **no PyAV**: `scenedetect`'s
   opencv/headless/pyav backends are optional extras we don't request (it falls
   back to its default opencv backend, which uses our headless cv2). The GPU
   `ml` extras additionally drop PaddleOCR's redundant full-opencv build to keep
   one cv2 (see `requirements-ml.txt`).

## Further levers (not yet implemented — see NEXT_STEPS)

- **Cache by content hash**: identical re-uploads/segments reuse prior OCR.
