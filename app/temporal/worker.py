from __future__ import annotations

import asyncio
import logging

from temporalio.worker import Worker

from app.config import settings
from app.temporal.activities import collect_release_context_activity
from app.temporal.client import get_temporal_client
from app.temporal.workflows import ControlledReleaseWorkflow

logger = logging.getLogger(__name__)


async def _run_worker_forever() -> None:
    while True:
        try:
            client = await get_temporal_client()
            worker = Worker(
                client,
                task_queue=settings.TEMPORAL_TASK_QUEUE,
                workflows=[ControlledReleaseWorkflow],
                activities=[collect_release_context_activity],
            )
            logger.info(
                "Starting Temporal worker for task queue '%s' at '%s'.",
                settings.TEMPORAL_TASK_QUEUE,
                settings.TEMPORAL_ADDRESS,
            )
            await worker.run()
        except Exception as exc:
            logger.exception("Temporal worker stopped unexpectedly: %s", exc)
            await asyncio.sleep(5)


def main() -> None:
    asyncio.run(_run_worker_forever())


if __name__ == "__main__":
    main()
