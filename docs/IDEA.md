# ScamShield — Team Brief

> **🇷🇺 Russian version:** [`IDEA.ru.md`](IDEA.ru.md)

## The product

**ScamShield** — a cross-platform (iPhone + Android) web app. You **paste or share
a real TikTok / Instagram / YouTube Shorts link** and get an instant, explainable
scam verdict: a risk score, the category (illegal casino, pyramid scheme,
"guaranteed income" fraud…), and the exact phrases that triggered it.

It's "antivirus for scam videos": you keep watching in your normal apps, and when
something feels off, you check it through ScamShield before you act.

## Key decisions (and why)

- ❌ **No "watch other apps" overlay.** Impossible on iOS — Apple forbids one app
  from seeing another app's screen/audio. It's a hard wall, not a skill gap.
- ✅ **Web app (PWA), opens via QR, no install.** Runs identically on both phones.
- ✅ **Backend downloads the *real* video by link (`yt-dlp`) and analyzes it
  server-side.** People keep using their normal apps; our system understands real
  platform content.
- ✅ **Whisper runs server-side, not on-device.** Simpler, and still 100%
  self-hosted (no cloud AI) — so the 20-point "independent AI model" criterion is
  safe.

## Who owns what

| Person | Job |
|---|---|
| **Backend (Mansur)** | Reuse the existing engine; add the `yt-dlp` downloader + the independent run-config; expose it via ngrok. (Plan: `docs/superpowers/plans/2026-06-24-scamshield-backend.md`.) |
| **Frontend** | The PWA: paste/share input → call the API → show the result screen (score, category, reason, evidence phrases). QR onboarding. Interface = `docs/API_CONTRACTS.md`. |
| **ML** | Add **Russian + Kazakh** scam phrases to the detector (`services/text_risk.py`, currently English-only); pick the Whisper model; **gather ~6–10 real demo clips** (scam + clean). |

## How it works (one video)

1. App sends the **link** to the backend.
2. Backend **downloads the real video** (`yt-dlp`: TikTok, IG, Shorts).
3. Backend runs the existing pipeline: **Whisper** (audio→text) + on-screen text →
   risk scoring → **explainable verdict**.
4. App shows: score, category, plain-language reason, and the phrases that gave it away.

## Why we win (judging criteria, 20 pts each)

1. **Relevance + AI** — real protection against the exact harms the track names.
2. **Independent AI model** — Whisper + our own deterministic engine, **zero
   external AI services**. (Most teams will fail this; we won't.)
3. **Security + ethics + explainability** — every verdict traces to its evidence.
4. **Practical + scalable** — no install, QR, every phone, one backend scales.
5. **Demo + defense** — live phone, real video, visible verdict in seconds.

## To confirm at the sync

1. Is **server-side Whisper** (not on-device) OK with everyone? (Changes the pitch.)
2. Who **gathers the demo clips**, and by when? (Blocks the demo rehearsal.)
3. What's the frontend built in (React / plain JS)?
4. Everyone agrees the user is the **consumer** (not the AFM analyst tool)?

## Demo (30 seconds on stage)

Open a real casino-scam TikTok → copy link → paste into ScamShield → ~few seconds →
**⚠️ "Незаконное казино — 87%"** with the spoken phrases. Then a normal cooking
video → **✅ "Безопасно."** (Optional: Wi-Fi off, re-run, to prove full independence.)
