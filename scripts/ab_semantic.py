#!/usr/bin/env python
"""A/B one video: lexicon-only vs lexicon + semantic layer.

Runs the SAME prepared video (same frames/audio/OCR/speech) through the analysis
brain twice — once with the semantic matcher off, once on — so the only variable
is the semantic layer. Prints a side-by-side diff so you can see what it changed.

Usage:
    pip install -r requirements-ml.txt          # PaddleOCR + Whisper + sentence-transformers
    PYTHONPATH=src python scripts/ab_semantic.py path/to/video.mp4

Notes:
- Uses real OCR + Whisper (semantic is pointless on the scripted mock text).
- Visual is disabled and the judge is the deterministic on-box fallback, so the
  run is fully local (the sovereign profile) and reproducible. No API, no DB.
- First run downloads the embedding model (~470MB) and the Whisper model.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

# Force the local sovereign profile before importing app code (settings read env).
os.environ.setdefault("AIMW_OCR_PROVIDER", "real")
os.environ.setdefault("AIMW_SPEECH_PROVIDER", "real")
os.environ.setdefault("AIMW_VISUAL_PROVIDER", "none")
os.environ.setdefault("AIMW_LOG_LEVEL", "WARNING")

from aimw.config import Settings  # noqa: E402
from aimw.domain.models import AnalysisArtifacts  # noqa: E402
from aimw.orchestration.container import build_container  # noqa: E402
from aimw.orchestration.orchestrator import AnalysisOrchestrator  # noqa: E402
from aimw.utils.ids import new_video_id  # noqa: E402


def _is_semantic(ev) -> bool:
    return bool(ev.matched_terms) and ev.matched_terms[0].startswith("~")


def _summary(art: AnalysisArtifacts) -> dict:
    r = art.report
    sem = [e for e in art.text_risk if _is_semantic(e)]
    return {
        "risk_score": r.risk_score,
        "category": r.category.value,
        "confidence": round(r.confidence, 3),
        "events": len(art.graph.events),
        "text_evidence": len(art.text_risk),
        "semantic_hits": len(sem),
        "categories": sorted({e.category.value for e in art.text_risk}),
        "_sem": sem,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    args = ap.parse_args()
    if not args.video.exists():
        ap.error(f"no such file: {args.video}")

    vid = new_video_id()

    # Prepare once (shared) so OCR/speech input is identical across both runs.
    base_orch = AnalysisOrchestrator(build_container(Settings(semantic_provider="off")))
    prepared = base_orch.prepare(video_id=vid, path=str(args.video), filename=args.video.name)

    base = _summary(asyncio.run(base_orch.run(prepared)))
    sem_orch = AnalysisOrchestrator(build_container(Settings(semantic_provider="local")))
    sem = _summary(asyncio.run(sem_orch.run(prepared)))

    w = 18
    print(f"\n  {'metric':<{w}}{'lexicon-only':<18}{'+ semantic':<18}")
    print(f"  {'-'*52}")
    for k in ("risk_score", "category", "confidence", "events", "text_evidence", "semantic_hits"):
        print(f"  {k:<{w}}{str(base[k]):<18}{str(sem[k]):<18}")
    print(f"  {'categories':<{w}}{','.join(base['categories']) or '-'}")
    print(f"  {'':<{w}}{'':<18}{','.join(sem['categories']) or '-'}")

    added = set(sem["categories"]) - set(base["categories"])
    print(f"\n  categories the semantic layer added: {sorted(added) or 'none'}")
    if sem["_sem"]:
        print("  semantic hits (paraphrases the lexicon missed):")
        for e in sem["_sem"][:10]:
            print(f"    [{e.timestamp:6.1f}s] {e.category.value:<22} {e.matched_terms[0]}  «{e.text[:60]}»")
    print()


if __name__ == "__main__":
    main()
