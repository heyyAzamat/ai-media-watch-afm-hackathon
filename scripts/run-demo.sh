#!/usr/bin/env bash
# ScamShield demo launcher.
# Starts the backend (uvicorn :8010) + a public cloudflared tunnel, then prints
# the exact URL to put in your demo QR code. Keep this terminal open during the
# demo, and keep the laptop awake.
#
# Usage:  bash scripts/run-demo.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
VERCEL_UI="https://scamshield-lyart.vercel.app"
PORT=8010
cd "$REPO"

# 1. venv
if [ ! -x .venv/bin/uvicorn ]; then
  echo "No .venv found. Run: python3 -m venv .venv && . .venv/bin/activate && pip install -e . faster-whisper"
  exit 1
fi
. .venv/bin/activate

# 2. backend
echo "Starting backend on :$PORT ..."
uvicorn aimw.main:app --host 0.0.0.0 --port "$PORT" >/tmp/scamshield-api.log 2>&1 &
API_PID=$!
# Startup loads Whisper + the semantic model (~30-60s on first run); poll health.
echo "  loading models (Whisper + semantic), up to ~90s…"
UP=0
for _ in $(seq 1 45); do
  if curl -fsS "localhost:$PORT/health" >/dev/null 2>&1; then UP=1; break; fi
  sleep 2
done
[ "$UP" = "1" ] && echo "  backend up (pid $API_PID)" || { echo "  backend failed — see /tmp/scamshield-api.log"; exit 1; }

# 3. tunnel
CF="$(command -v cloudflared || echo "$HOME/.local/bin/cloudflared")"
echo "Starting public tunnel ..."
"$CF" tunnel --url "http://localhost:$PORT" >/tmp/scamshield-tunnel.log 2>&1 &
TUNNEL_PID=$!
for _ in $(seq 1 20); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/scamshield-tunnel.log | head -1 || true)"
  [ -n "${URL:-}" ] && break
  sleep 1
done
[ -z "${URL:-}" ] && { echo "  tunnel URL not found — see /tmp/scamshield-tunnel.log"; exit 1; }
echo "  tunnel up (pid $TUNNEL_PID): $URL"

echo ""
echo "=================================================================="
echo " DEMO IS LIVE. Put THIS URL in your QR code:"
echo ""
echo "   $VERCEL_UI/?api=$URL"
echo ""
echo " (Or open the backend-served UI directly: $URL/app/ )"
echo "=================================================================="
echo "Press Ctrl+C to stop both the backend and the tunnel."
trap 'kill $API_PID $TUNNEL_PID 2>/dev/null; echo "stopped."' INT TERM
wait
