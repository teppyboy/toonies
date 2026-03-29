"""
Per-connection handler. Mirrors toonies-server/src/connection.rs.

Each accepted TCP connection gets its own task running handle_connection().
It maintains a broadcast subscription queue and multiplexes between:
  - incoming client messages (read from socket)
  - outgoing broadcast messages (from the server's broadcast fan-out)
"""
import asyncio

import structlog

from toonies_server import handler
from toonies_server.exceptions import ProtocolError
from toonies_server.protocol import codec, framing
from toonies_server.state.store import AppState

logger = structlog.get_logger()


async def handle_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    state: AppState,
) -> None:
    peer = writer.get_extra_info("peername", "<unknown>")
    logger.info("client_connected", peer=str(peer))

    broadcast_q = state.subscribe()
    try:
        await _run(reader, writer, state, broadcast_q)
    finally:
        state.unsubscribe(broadcast_q)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        logger.info("client_disconnected", peer=str(peer))


async def _run(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    state: AppState,
    broadcast_q: asyncio.Queue,
) -> None:
    read_task = asyncio.create_task(_read_one(reader))
    bcast_task = asyncio.create_task(broadcast_q.get())

    while True:
        done, pending = await asyncio.wait(
            {read_task, bcast_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if read_task in done:
            exc = read_task.exception()
            if exc is not None:
                if not isinstance(exc, ProtocolError):
                    logger.warning("read_error", error=str(exc))
                # Cancel bcast task and exit
                bcast_task.cancel()
                return

            raw = read_task.result()
            if raw is None:
                bcast_task.cancel()
                return

            try:
                msg = codec.decode(raw)
            except ProtocolError as e:
                logger.warning("decode_error", error=str(e))
                read_task = asyncio.create_task(_read_one(reader))
                continue

            responses = await handler.process(msg, state)
            for resp in responses:
                try:
                    await framing.write_frame(writer, codec.encode(resp))
                except Exception as e:
                    logger.warning("write_error", error=str(e))
                    bcast_task.cancel()
                    return

            read_task = asyncio.create_task(_read_one(reader))

        if bcast_task in done:
            bcast_exc = bcast_task.exception()
            if bcast_exc is not None:
                logger.warning("broadcast_queue_error", error=str(bcast_exc))
                read_task.cancel()
                return

            broadcast_msg = bcast_task.result()
            try:
                await framing.write_frame(writer, codec.encode(broadcast_msg))
            except Exception as e:
                logger.warning("write_error", error=str(e))
                read_task.cancel()
                return

            bcast_task = asyncio.create_task(broadcast_q.get())


async def _read_one(reader: asyncio.StreamReader) -> bytes | None:
    """Read one frame. Returns None on clean EOF, raises ProtocolError on error."""
    try:
        return await framing.read_frame(reader)
    except ProtocolError:
        raise
    except Exception as e:
        raise ProtocolError(str(e)) from e
