"""Aggregate v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from .endpoints import analyze, evidence, report, risk, status, timeline

api_router = APIRouter()
api_router.include_router(analyze.router, tags=["analysis"])
api_router.include_router(status.router, tags=["analysis"])
api_router.include_router(report.router, tags=["results"])
api_router.include_router(timeline.router, tags=["results"])
api_router.include_router(evidence.router, tags=["results"])
api_router.include_router(risk.router, tags=["results"])
