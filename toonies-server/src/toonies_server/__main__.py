import asyncio
import sys

import structlog

from toonies_server.config import DEFAULT_HOST, DEFAULT_PORT
from toonies_server.server import run
from toonies_server.state.store import AppState


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def main() -> None:
    _configure_logging()

    host = DEFAULT_HOST
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        addr = sys.argv[1]
        if ":" in addr:
            h, p = addr.rsplit(":", 1)
            host = h
            port = int(p)
        else:
            port = int(addr)

    state = AppState()
    asyncio.run(run(host, port, state))


if __name__ == "__main__":
    main()
