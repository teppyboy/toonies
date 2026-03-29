"""
TCP server accept loop. Mirrors toonies-server/src/server.rs.
"""
import asyncio
import signal

import structlog

from toonies_server.connection import handle_connection
from toonies_server.protocol.codec import make_server_message, encode
from toonies_server.protocol.framing import write_frame
from toonies_server.state.store import AppState

logger = structlog.get_logger()


async def run(host: str, port: int, state: AppState) -> None:
    server = await asyncio.start_server(
        lambda r, w: handle_connection(r, w, state),
        host,
        port,
    )

    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    logger.info("server_started", address=addrs)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _on_signal():
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler for all signals
            pass

    async with server:
        try:
            await stop_event.wait()
        except asyncio.CancelledError:
            pass

    logger.info("server_shutting_down")
    shutdown_msg = make_server_message("ServerShutdown", message="Server is shutting down")
    for q in list(state._subscribers):
        try:
            q.put_nowait(shutdown_msg)
        except asyncio.QueueFull:
            pass
