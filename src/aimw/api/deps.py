"""FastAPI dependencies: DB sessions and repositories (dependency injection)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from ..db.base import get_session
from ..db.repositories import ArtifactRepository, JobRepository, VideoRepository


def get_db() -> Iterator[Session]:
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_job_repo(db: Session = Depends(get_db)) -> JobRepository:
    return JobRepository(db)


def get_video_repo(db: Session = Depends(get_db)) -> VideoRepository:
    return VideoRepository(db)


def get_artifact_repo(db: Session = Depends(get_db)) -> ArtifactRepository:
    return ArtifactRepository(db)
