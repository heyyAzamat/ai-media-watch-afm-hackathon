"""Run the full analysis engine on a local file WITHOUT Celery or a database.

Useful for demos, debugging and CI smoke tests. With the default mock providers
it requires no GPU and no external services.

Usage:
    python -m aimw.scripts.run_local /path/to/video.mp4
    python -m aimw.scripts.run_local            # synthetic run (no file needed)
"""

from __future__ import annotations

import asyncio
import sys

import orjson

from ..logging_config import configure_logging, get_logger
from ..orchestration.orchestrator import AnalysisOrchestrator
from ..utils.ids import new_video_id

log = get_logger(__name__)


async def _run(path: str | None) -> None:
    orchestrator = AnalysisOrchestrator()
    video_id = new_video_id()
    prepared = orchestrator.prepare(
        video_id=video_id,
        path=path or "(synthetic)",
        filename=path.split("/")[-1] if path else "synthetic.mp4",
    )
    artifacts = await orchestrator.run(prepared)
    print(orjson.dumps(artifacts.report.model_dump(mode="json"), option=orjson.OPT_INDENT_2).decode())


def main() -> None:
    configure_logging(json_output=False)
    path = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(_run(path))


if __name__ == "__main__":
    main()
