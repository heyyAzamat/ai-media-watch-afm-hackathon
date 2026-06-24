#!/usr/bin/env python
"""Minimal upload-and-inspect UI — no DB, no Redis, no Celery.

Runs the framework-agnostic orchestrator in-process: upload a video, get the risk
metrics and a player with clickable markers at each suspicious timestamp. Respects
.env (sovereign profile by default), so it uses whatever providers are configured.

    PYTHONPATH=src python scripts/simple_ui.py        # then open http://localhost:8000

Needs the real providers' deps if .env selects them:  pip install -r requirements-ml.txt
ponytail: single-user local demo — analysis runs inline on the event loop (~20s on
CPU) and the orchestrator (models) is built once and reused. Add a job queue only
if you need concurrent users (that's what the full src/aimw/api + Celery path is for).
"""

from __future__ import annotations

import html
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from aimw.config import get_settings
from aimw.domain.models import AnalysisReport
from aimw.orchestration.orchestrator import AnalysisOrchestrator
from aimw.utils.ids import new_video_id

app = FastAPI(title="AI Media Watch — demo")
_orch: AnalysisOrchestrator | None = None  # built lazily so import stays light


def orchestrator() -> AnalysisOrchestrator:
    global _orch
    if _orch is None:
        _orch = AnalysisOrchestrator()  # loads configured models once
    return _orch


UPLOAD_FORM = """<!doctype html><meta charset=utf-8>
<title>AI Media Watch</title>
<style>
 body{font:16px/1.5 system-ui;max-width:760px;margin:40px auto;padding:0 16px;color:#1a1a1a}
 h1{font-size:22px} .drop{border:2px dashed #bbb;border-radius:10px;padding:32px;text-align:center}
 button{font:inherit;padding:10px 20px;border:0;border-radius:8px;background:#1a56db;color:#fff;cursor:pointer}
 .hint{color:#666;font-size:14px}
</style>
<h1>AI Media Watch — video risk analysis</h1>
<form class=drop method=post action=/analyze enctype=multipart/form-data>
 <p>Upload a video (mp4 / mov / webm)</p>
 <p><input type=file name=file accept="video/*" required></p>
 <p><button type=submit>Analyze</button></p>
 <p class=hint>Runs locally. Analysis can take ~20s on CPU — the page will wait.</p>
</form>"""

_SEV_COLOR = {"high": "#d92d20", "medium": "#e07a00", "low": "#b59000"}


def _results_page(report: AnalysisReport, media_url: str) -> str:
    e = html.escape
    rows = "".join(
        f"<tr><td>{e(k)}</td><td><b>{e(str(v))}</b></td></tr>"
        for k, v in {
            "Risk score": f"{report.risk_score} / 100",
            "Category": report.category.value,
            "Confidence": f"{report.confidence:.2f}",
            "LLM judge used": "yes (remote)" if report.llm_called else "no (on-box fallback)",
            "Fallback verdict": "yes" if report.fallback_used else "no",
            "Suspicious moments": len(report.player_markers),
        }.items()
    )

    markers = report.player_markers or []
    if markers:
        items = "".join(
            f'<li><button class=jump data-ts="{m.timestamp}" '
            f'style="border-left:6px solid {_SEV_COLOR.get(m.severity.value, "#888")}">'
            f"{m.icon} <b>{e(m.display_time)}</b> — {e(m.label)} "
            f"<span class=sev>({e(m.severity.value)})</span></button></li>"
            for m in markers
        )
        markers_html = f"<ul class=markers>{items}</ul>"
    else:
        markers_html = "<p class=hint>No suspicious moments detected.</p>"

    timeline = "".join(
        f"<tr><td>{m.start:.1f}–{m.end:.1f}s</td><td>{e(m.category.value)}</td>"
        f"<td>{e(m.severity.value)}</td><td>{m.confidence:.2f}</td>"
        f"<td>{e('; '.join(m.evidence[:3]))}</td></tr>"
        for m in report.timeline
    )

    summary = e(report.summary or "—")
    explanation = e(report.explanation or "")
    return f"""<!doctype html><meta charset=utf-8>
<title>Result — AI Media Watch</title>
<style>
 body{{font:16px/1.5 system-ui;max-width:900px;margin:32px auto;padding:0 16px;color:#1a1a1a}}
 h1{{font-size:22px}} h2{{font-size:17px;margin-top:28px}}
 video{{width:100%;max-height:460px;background:#000;border-radius:10px}}
 table{{border-collapse:collapse;width:100%}} td,th{{padding:6px 10px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}}
 .markers{{list-style:none;padding:0}} .markers li{{margin:6px 0}}
 .jump{{font:inherit;cursor:pointer;background:#f6f7f9;border:0;border-radius:6px;padding:8px 12px;width:100%;text-align:left}}
 .jump:hover{{background:#eef1f6}} .sev{{color:#666}}
 a{{color:#1a56db}}
</style>
<h1>Analysis result</h1>
<video id=v src="{media_url}" controls preload=metadata></video>

<h2>Metrics</h2>
<table>{rows}</table>
<p><b>Summary:</b> {summary}</p>
{f'<p><b>Why:</b> {explanation}</p>' if explanation else ''}

<h2>Suspicious moments <span class=hint>(click to jump)</span></h2>
{markers_html}

<h2>Timeline</h2>
<table>
 <tr><th>When</th><th>Category</th><th>Severity</th><th>Conf.</th><th>Evidence</th></tr>
 {timeline or '<tr><td colspan=5>No timeline events.</td></tr>'}
</table>

<p><a href="/">← analyze another video</a></p>
<script>
 const v = document.getElementById('v');
 for (const b of document.querySelectorAll('.jump'))
   b.onclick = () => {{ v.currentTime = parseFloat(b.dataset.ts); v.play(); v.scrollIntoView({{behavior:'smooth'}}); }};
</script>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return UPLOAD_FORM


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(file: UploadFile = File(...)) -> str:
    settings = get_settings()
    settings.ensure_dirs()
    ext = (Path(file.filename or "video.mp4").suffix.lstrip(".") or "mp4").lower()
    if ext not in settings.allowed_extension_set:
        return f"<p>Unsupported file type '.{html.escape(ext)}'. " \
               f"Allowed: {sorted(settings.allowed_extension_set)}.</p><p><a href=/>back</a></p>"

    video_id = new_video_id()
    dest = settings.uploads_dir / f"{video_id}.{ext}"
    dest.write_bytes(await file.read())

    try:
        orch = orchestrator()
        prepared = orch.prepare(video_id=video_id, path=str(dest), filename=dest.name)
        artifacts = await orch.run(prepared)
    except Exception as exc:  # noqa: BLE001 — surface any pipeline error to the page
        return f"<h1>Analysis failed</h1><pre>{html.escape(type(exc).__name__)}: " \
               f"{html.escape(str(exc))}</pre><p><a href=/>back</a></p>"

    return _results_page(artifacts.report, media_url=f"/media/{dest.name}")


@app.get("/media/{name}")
def media(name: str) -> FileResponse:
    path = get_settings().uploads_dir / Path(name).name  # basename only — no traversal
    return FileResponse(path)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
