# ScamShield — Consumer Scam-Video Detection (Design Spec)

**Date:** 2026-06-24
**Context:** AFM AI Hackathon 2026, Track 3 ("AI Media Watch"). Finals 2026-06-25.
**Team:** 3 people — frontend (web), backend (Mansur, beginner), ML.
**Status:** Approved direction; ready for implementation planning.

---

## 1. One-line summary

A cross-platform (iOS + Android) app where a user **shares or pastes a real
TikTok / Instagram / YouTube Shorts link** and gets, within a few seconds, an
**explainable scam verdict** — risk score, category, and the exact spoken/on-screen
phrases that triggered it.

It is "antivirus for scam videos": the user keeps watching in their normal apps,
and when something feels off, they check it through ScamShield before they act.

## 2. Why this shape (decisions already made)

- **Cross-platform requirement kills native overlays.** iOS forbids one app from
  watching another app's screen/audio. There is no workaround. So a silent
  "watch-along inside TikTok" is impossible on iOS and was rejected.
- **Server-side analysis of the real video** is the cross-platform answer: the
  user hands us a *link*, the backend downloads the *real* video and analyzes it.
  People keep using their normal apps; our system understands real platform content.
- **Frontend = a mobile web app (PWA).** Runs identically on iOS + Android, no
  install, opens via QR. Built with the frontend dev's existing web skills.
- **Whisper runs server-side** (faster-whisper, self-hosted). Decided trade-off:
  simpler and reliable; still **no external AI service** (criterion #2 holds).
  On-device Whisper was only relevant to the rejected live-feed model.

## 3. Goals / Non-goals

### Goals
1. Submit a TikTok/IG/Shorts URL (or upload a file) → get an explained scam verdict.
2. Verdict is **explainable**: score + category + the evidence (phrases, timestamps).
3. Runs on iPhone and Android via one web codebase; onboarding by QR.
4. **Zero external AI dependency** — Whisper + OCR + risk engine all self-hosted/local.
5. Reliable live demo in <5 seconds of stage time per check.

### Non-goals (explicitly cut for time)
- ❌ Watching other apps' screens (impossible on iOS).
- ❌ User accounts / auth / multi-tenant.
- ❌ Continuous crawling of platforms (that is the *regulator* product, not this).
- ❌ The OpenRouter LLM judge and the Qwen-VL visual model (both external) — see §7.
- ❌ Native iOS/Android apps or share-extensions requiring mobile devs.

## 4. User flows

1. **Paste a link (primary, reliable on all phones):** copy a TikTok/IG/Shorts URL
   → open ScamShield (QR/bookmark) → paste → "Check" → see verdict.
2. **Share-to-app (Android bonus):** Share → ScamShield (Web Share Target on
   Android Chrome). iOS PWA share-target is unreliable, so paste is the dependable
   path there.
3. **Upload a saved video (fallback):** pick an mp4/mov/webm from the device.

## 5. Architecture

```
   PHONE (mobile web app / PWA)                BACKEND (existing FastAPI, reused)
   ─────────────────────────────              ─────────────────────────────────────
   paste/share/upload  ─────────POST /analyze──────►  download real video (yt-dlp)
        │                                                     │
        │                                             prepare (frames + audio)
        │                                                     │
        │                                       Whisper (local) + PaddleOCR (local)
        │                                                     │
        │                                       text-risk → fusion → timeline
        │                                                     │
        │                                       deterministic verdict (no network)
        │◄──── poll GET /status ──── job progresses ──────────┘
        │◄──── GET /report ──────── final explainable report
   render verdict (score, category, reason, evidence phrases + timestamps)
```

The backend is the **existing engine, reused almost wholesale.** The only genuinely
new backend code is the platform downloader.

## 6. Components & ownership

### 6.1 Backend (Mansur) — mostly wiring, little new code
- **`yt-dlp` downloader** — the one real new piece. Replace/extend
  `api/v1/endpoints/analyze.py::_download_url` so a TikTok/IG/Shorts page URL is
  downloaded via `yt-dlp` to an mp4. Direct media URLs keep working via the
  current httpx path. Add `yt-dlp` to dependencies.
- **Run configuration (env)** for a 100%-independent, reliable demo:
  - `AIMW_SPEECH_PROVIDER=real` (faster-whisper, local)
  - `AIMW_OCR_PROVIDER=real` (PaddleOCR, local)
  - `AIMW_VISUAL_PROVIDER=mock` (skip the external Qwen-VL; audio+OCR is the core)
  - `AIMW_WHISPER_MODEL=base` (or `small`) — far faster than the `large-v3` default
  - **No `AIMW_OPENROUTER_API_KEY`** → `build_reasoning_engine()` auto-selects the
    deterministic `FallbackReasoningEngine` (`reasoning/base.py`). No network, no
    external AI. This is the key to criterion #2.
- **Reachability:** CORS is already wide-open (`main.py`). Expose the laptop to the
  phone via a tunnel (`ngrok http 8000`) or same-Wi-Fi LAN IP.
- **(Optional, if time) speed tuning:** cap analyzed duration / lower
  `AIMW_FRAMES_PER_SECOND` for snappier verdicts on long videos.

The API contract is **unchanged** — see §8. Frontend uses the existing endpoints.

### 6.2 Frontend (frontend dev) — the new surface
- Mobile-first PWA: paste/share/upload input, a "Checking…" progress state, and a
  result screen (score dial, category, plain-language reason, list of evidence
  phrases with timestamps). A QR code (just a link to the app URL) for onboarding.
- Talks to the backend: `POST /analyze` (with `source_url`), poll `GET /status/{id}`
  every ~1.5s, then `GET /report/{id}` on completion. Render `report`.

### 6.3 ML (ML dev)
- **Russian + Kazakh scam lexicons** added to `services/text_risk.py` (currently
  English-only). Essential for KZ content and a real detection-quality win.
- Pick the Whisper model size (start `base`, validate quality vs speed).
- **Gather ~6–10 real demo clips** (mix of casino/pyramid/"guaranteed income"
  scams + clean controls) — also the test set for tuning detection.

## 7. Independence (criterion #2) — the 20-point defense

With the §6.1 config, every AI component is self-hosted/local:
- **Whisper** (faster-whisper) — local.
- **PaddleOCR** — local.
- **Text-risk + fusion + verdict** — our own deterministic algorithms, no network.

The external pieces (OpenRouter LLM judge, Qwen-VL visual) are **turned off** for
the demo. The system produces a complete, explainable verdict with the internet
disconnected. Stage move: run a check with Wi-Fi off to prove it.

## 8. API contract (reused, unchanged)

`POST /api/v1/analyze` (multipart form):
- `source_url` — the TikTok/IG/Shorts link (or `file` for upload)
- `source_platform` — `tiktok` | `instagram` | `youtube` | `upload`
- → `202 { job_id, video_id, status, poll_url }`

`GET /api/v1/status/{job_id}` → `{ status, progress, stage_detail }`
`GET /api/v1/report/{job_id}` → full explainable report:
`{ risk_score, category, confidence, summary, explanation, timeline[], evidence{} }`

(Full shapes in `docs/API_CONTRACTS.md`.)

## 9. Error handling

- **Download fails** (private/removed video, unsupported URL): backend returns a
  clear `400` from `_download_url`; frontend shows "Couldn't fetch this video — try
  uploading it instead."
- **Analysis error:** job → `failed` with an error string; frontend shows a retry.
- **Slow video:** progress states keep the user informed; cap duration if needed.
- **No scam found:** verdict `category=none`, score low → frontend shows ✅ "Safe."
- The deterministic judge means analysis **cannot fail due to a missing API/network.**

## 10. Testing

- **Reused:** existing 19 unit/integration tests (mock providers, offline) must
  still pass (`make test`).
- **New:** a unit test for the `yt-dlp` downloader path (mock the downloader; assert
  a saved file path + correct error on failure). Do not hit the network in tests.
- **Manual demo rehearsal:** run the real pipeline on each of the ~6–10 demo clips;
  confirm scam clips score high with sensible evidence and clean clips score low.

## 11. Demo script (stage)

1. Show the phone (QR → app already open).
2. Paste a **real casino-scam TikTok** link → "Check" → ~few seconds →
   **⚠️ "Незаконное казино — 87%"** with the spoken phrases that gave it away.
3. Paste a **normal cooking video** → **✅ "Безопасно."**
4. (Optional) turn Wi-Fi off on the laptop and re-run to prove full independence.

## 12. Criteria mapping

| Criterion (20 pts each) | How we hit it |
|---|---|
| 1. Relevance + AI justification | Real-time-ish protection against the exact harms the track names |
| 2. Independent AI model | Whisper + OCR + deterministic engine, **zero external AI** (§7) |
| 3. Security + ethics + explainability | Every verdict traces to specific evidence (no black box); analysis is local so content never leaves our own infrastructure |
| 4. Practical + scalable | No install, QR, every phone; one backend scales |
| 5. Demo + technical defense | Live phone, real video, visible verdict in seconds |

## 13. Risks & mitigations

- **`yt-dlp` blocked by a platform** (login walls, region blocks) → fall back to the
  **upload** flow; pre-download demo clips so the stage demo never depends on live
  scraping.
- **Whisper too slow on CPU** → use `base`/`tiny`, cap duration, pre-warm the model.
- **Detection misses RU/KZ content** → ML adds RU/KZ lexicons (§6.3) before the demo.
- **Beginner backender** → scope is wiring + config, not new architecture; pair with
  this assistant step by step.

## 14. Build order (for the implementation plan)

1. Backend: add `yt-dlp` downloader + run config; verify `POST /analyze` with a real
   TikTok URL produces a sensible report end-to-end. **(Mansur — highest priority.)**
2. Backend: expose via ngrok; confirm a phone browser can reach `/docs` and analyze.
3. Frontend: paste→analyze→poll→render result screen + QR onboarding.
4. ML: RU/KZ lexicons + demo clips + Whisper model choice.
5. Integration + demo rehearsal on all demo clips; record a backup screen capture.
