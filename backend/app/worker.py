from __future__ import annotations

import logging
import os
import time

from app.core.monitoring import run_due_collections
from app.core.stores import monitoring_store

logger = logging.getLogger(__name__)


def main(poll_seconds: int = 60) -> None:
    while True:
        try:
            results = run_due_collections(monitoring_store)
            if results:
                logger.info("Completed %d scheduled collection(s).", len(results))
        except Exception:
            logger.exception("Scheduled collection cycle failed.")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    main(max(15, int(os.getenv("MONITOR_POLL_SECONDS", "60"))))
