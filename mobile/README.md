# Media Watch (mobile)

Media Watch is an [Expo](https://expo.dev/) (React Native) mobile client for the
**AI Media Watch** video-risk-analysis backend. You paste a video or profile
link (or upload a video file), the app submits it for analysis, polls the job to
completion, and renders a risk report that flags **gambling, scam, and
hidden-advertising** content found in the media.

It talks to the FastAPI backend in `../src/aimw` using its async job flow:

```
POST /api/v1/analyze        -> 202 { job_id, video_id, ... }   (submit URL or file)
GET  /api/v1/status/{job_id}                                    (poll until terminal)
GET  /api/v1/report/{video_id}                                 (fetch the report)
```

Built with Expo SDK 56, Expo Router (file-based routing, typed routes), React
19, and React Native 0.85. The UI is a dark-only "premium fintech" theme.

---

## Prerequisites

- **Node.js** (LTS) and npm.
- The **AI Media Watch backend running and reachable** from your device/emulator.
  See `../src/aimw`. The app expects it on `http://<host>:8000` and adds the
  `/api/v1` prefix itself (see "Configuring the API base URL").
- To run on a device/simulator:
  - **iOS**: Xcode + an iOS Simulator (macOS), or Expo Go on a physical device.
  - **Android**: Android Studio + an emulator, or Expo Go on a physical device.
- Optional: the [Expo](https://docs.expo.dev/) tooling is invoked via `npx`, so
  no global install is required.

> This project targets **Expo SDK 56**. Refer to the exact versioned docs at
> <https://docs.expo.dev/versions/v56.0.0/>.

---

## Install

From this `mobile/` directory:

```bash
npm install
```

---

## Run

Start the Metro dev server and choose a target:

```bash
npx expo start
```

Then press one of:

- `i` — open in the **iOS Simulator**
- `a` — open in the **Android emulator**
- `w` — open in a **web browser**

Or use the npm scripts directly:

```bash
npm run ios       # expo start --ios
npm run android   # expo start --android
npm run web       # expo start --web
npm start         # expo start
```

Other scripts:

```bash
npm run lint      # expo lint (eslint-config-expo)
```

---

## Configuring the API base URL

The app needs to reach the backend. The default base URL depends on the
platform (`src/constants/config.ts`):

- **iOS simulator** → `http://localhost:8000`
- **Android emulator** → `http://10.0.2.2:8000` (on Android `localhost` is the
  emulator itself, not your machine)
- **Physical device** → your computer's **LAN IP**, e.g. `http://192.168.x.x:8000`

You can override the base URL at runtime in the in-app **Settings** screen
(tap the ⚙ gear on the Home screen). Enter only the scheme + host + port — for
example `http://localhost:8000`. **Do not include `/api/v1`; the app appends it
automatically.** Settings are persisted on-device (AsyncStorage); use **Reset**
to return to the platform default.

---

## Screen flow

Routing is file-based via Expo Router (`src/app/`). The root layout
(`_layout.tsx`) wraps everything in an auth provider and redirects to Login when
there is no session, or to Home when an authenticated user lands on an auth
screen.

- **Login / Register** (`login.tsx`, `register.tsx`) —
  **⚠️ Authentication is a LOCAL MOCK placeholder.** There is no auth backend.
  Accounts and the active session are stored **unencrypted on-device** in
  AsyncStorage (`src/storage/auth.ts`, plaintext — not secure). Sign-up requires
  a name, email, and a password of at least 4 characters; sign-in checks the
  email/password against the locally stored accounts. This exists only so the
  flow works end-to-end and is meant to be swapped for real `/auth` API calls
  later.
- **Home / scan** (`index.tsx`) — the main scan screen. A **Video / Profile**
  segmented toggle, a **paste-link** field (validated for `http(s)://`), an
  **Analyze** button, and an **"or upload a video file"** action that opens the
  document picker (`video/*`). Submitting a link or file calls `POST /analyze`,
  saves the returned job locally, and navigates to the Job detail screen. Shows
  your most recent scans with a "See all" link to History.
- **Job detail** (`job/[id].tsx`) — **live polling**. Polls
  `GET /status/{job_id}` every 2 s (`POLL_INTERVAL_MS`), showing a progress bar
  and stage detail while the job runs. On `completed` it fetches
  `GET /report/{video_id}` and renders the **risk report**: a score ring +
  category + confidence, a summary/explanation, an evidence-marker player, a
  severity-coded timeline, evidence counts (on-screen text / speech / visual),
  extracted OCR & speech snippets, and video metadata. Handles `failed` jobs and
  unreachable-API errors.
- **History** (`history.tsx`) — all locally tracked scans, pull-to-refresh, and
  a **Clear history** action. Job history is **local-only** (see Known
  limitations).
- **Settings** (`settings.tsx`) — shows the current account, lets you edit/reset
  the **API base URL**, and **Sign out**.

---

## Project structure

```
mobile/
├─ app.json            Expo app config ("Media Watch", scheme "mediawatch", dark UI)
├─ package.json        Dependencies + scripts (start / ios / android / web / lint)
├─ tsconfig.json       Strict TS; "@/*" -> "./src/*", "@/assets/*" -> "./assets/*"
├─ assets/             Icons, splash, images
└─ src/
   ├─ app/             Expo Router routes (file-based)
   │  ├─ _layout.tsx   Root stack + auth-gated navigation
   │  ├─ index.tsx     Home / scan
   │  ├─ login.tsx     Login (mock auth)
   │  ├─ register.tsx  Register (mock auth)
   │  ├─ history.tsx   Scan history (local)
   │  ├─ settings.tsx  API URL + account + sign out
   │  └─ job/[id].tsx  Job detail: polling + risk report
   ├─ api/             Typed backend client
   │  ├─ client.ts     submitAnalyze / getStatus / getReport / getRisk + ApiError
   │  └─ types.ts      Wire types mirroring the backend schema/enums
   ├─ auth/
   │  └─ auth-context.tsx   AuthProvider / useAuth (wraps storage/auth)
   ├─ storage/         AsyncStorage-backed persistence
   │  ├─ auth.ts       LOCAL MOCK auth (accounts + session, plaintext)
   │  ├─ jobs.ts       Tracked-jobs store (powers History)
   │  └─ settings.ts   Persisted API base URL
   ├─ components/      UI building blocks (Screen, ui.tsx, JobRow, ScoreRing, themed text)
   ├─ constants/       config.ts (URLs, poll interval), theme.ts (colors/spacing), risk.ts (labels/severity)
   └─ utils/           platform.ts (infer source platform from URL, URL helpers)
```

---

## Known limitations

- **Mock authentication.** Login/Register do not call any backend. Credentials
  are stored unencrypted on-device and are not secure — replace
  `src/storage/auth.ts` with real auth before any real use.
- **`source_url` must be a directly downloadable media URL.** When you paste a
  link, the app sends it to the backend as `source_url`. The backend downloads
  that URL directly, so it must point at an actual media file. Social-media
  **page** links (TikTok/Instagram/YouTube/etc. watch pages) will **not**
  download server-side without `yt-dlp` (or similar) on the backend. For
  reliable results, upload a video file or paste a direct media URL.
- **History is local-only.** The backend has **no "list jobs" endpoint**, so the
  app remembers every job it submits in on-device storage (`src/storage/jobs.ts`).
  History does not sync across devices and is lost if you clear it or reinstall.
