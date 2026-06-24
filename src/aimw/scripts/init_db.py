"""Create all tables (idempotent). For production, prefer Alembic migrations.

Usage:
    python -m aimw.scripts.init_db
"""

from __future__ import annotations

from ..db import models  # noqa: F401  (registers ORM tables on Base.metadata)
from ..db.base import Base, init_engine
from ..logging_config import configure_logging, get_logger


def main() -> None:
    configure_logging()
    log = get_logger(__name__)
    engine = init_engine()
    Base.metadata.create_all(engine)
    log.info("db.init.done", tables=sorted(Base.metadata.tables))


if __name__ == "__main__":
    main()
