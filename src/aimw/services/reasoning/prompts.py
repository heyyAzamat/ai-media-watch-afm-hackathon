"""Prompt construction for the final compliance-judge call (Step 10).

The judge receives a *compact, pre-digested* evidence package (not raw frames),
which is why the 72B model is called exactly once per video.
"""

from __future__ import annotations

import orjson

from ...domain.models import (
    EvidenceGraph,
    TextRiskEvidence,
    TimelineEvent,
    Transcript,
    VideoMetadata,
    VisualDetection,
)

SYSTEM_PROMPT = (
    "You are an expert compliance officer, financial-crime investigator, fraud "
    "analyst and gambling-regulation specialist. You analyze pre-extracted "
    "multimodal evidence from a social-media video and decide whether it promotes "
    "illegal online gambling, casinos, sports betting, financial pyramid/Ponzi "
    "schemes, guaranteed-income or referral scams, fake investments, or other "
    "fraudulent/high-risk financial content.\n\n"
    "Rules:\n"
    "- Base every conclusion ONLY on the supplied evidence; never invent facts.\n"
    "- Corroboration across modalities (OCR + speech + visual) increases confidence.\n"
    "- Cite concrete evidence and the timestamps that justify the score.\n"
    "- Output VALID JSON ONLY, no prose, matching the requested schema exactly."
)

_OUTPUT_SCHEMA = {
    "risk_score": "integer 0-100",
    "category": "one of the allowed category strings",
    "confidence": "float 0.0-1.0",
    "summary": "one-paragraph human-readable summary",
    "explanation": "reasoning grounded in the evidence",
    "supporting_evidence": ["short evidence strings"],
    "suspicious_timestamps": ["float seconds"],
}


def _compact(obj) -> str:  # noqa: ANN001
    return orjson.dumps(obj).decode("utf-8")


def build_user_prompt(
    *,
    metadata: VideoMetadata,
    ocr_risk: list[TextRiskEvidence],
    speech_risk: list[TextRiskEvidence],
    transcript: Transcript,
    visual: list[VisualDetection],
    graph: EvidenceGraph,
    timeline: list[TimelineEvent],
    allowed_categories: list[str],
) -> str:
    package = {
        "video": {
            "id": metadata.video_id,
            "duration_seconds": metadata.duration_seconds,
            "platform": metadata.source_platform,
            "resolution": metadata.resolution,
        },
        "transcript": transcript.full_text[:4000],
        "ocr_risk_evidence": [
            {"t": e.timestamp, "category": e.category, "conf": e.confidence,
             "terms": e.matched_terms, "text": e.text}
            for e in ocr_risk
        ],
        "speech_risk_evidence": [
            {"t": e.timestamp, "category": e.category, "conf": e.confidence,
             "terms": e.matched_terms, "text": e.text}
            for e in speech_risk
        ],
        "visual_detections": [
            {"t": d.timestamp, "top": d.top_label, "evidence": d.evidence}
            for d in visual
            if d.top_label and d.top_label[1] >= 0.5
        ],
        "fused_events": [
            {"start": ev.start, "end": ev.end, "category": ev.category,
             "conf": ev.confidence, "sources": [s.value for s in ev.sources]}
            for ev in graph.events
        ],
        "timeline": [
            {"start": ev.start, "end": ev.end, "severity": ev.severity,
             "category": ev.category, "evidence": ev.evidence}
            for ev in timeline
        ],
    }
    return (
        "ALLOWED_CATEGORIES = "
        + _compact(allowed_categories)
        + "\n\nOUTPUT_SCHEMA = "
        + _compact(_OUTPUT_SCHEMA)
        + "\n\nEVIDENCE_PACKAGE = "
        + _compact(package)
        + "\n\nReturn ONLY the JSON object described by OUTPUT_SCHEMA."
    )


REPAIR_PROMPT = (
    "Your previous response was not valid JSON matching OUTPUT_SCHEMA. "
    "Return ONLY a corrected JSON object, with no commentary."
)
