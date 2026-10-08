"""Central logging configuration."""

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
        force=True,
    )
    # SQL echo is noisy; enable explicitly when debugging.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
