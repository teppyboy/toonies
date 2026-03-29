"""
Background TCP networking task.
Mirrors toonies-client/src/network.rs.

Bridges the textual event loop and the server TCP connection via asyncio.Queue.
"""
import asyncio

from toonies_common import codec, framing
from toonies_common.exceptions import ProtocolError


class NetworkWorker:
    """Owns the TCP connection; driven by the App via send_queue."""

    def __init__(self, addr: str, on_event):
        self._addr = addr
        self._on_event = on_event  # callable(event_type: str, data)
        self.send_queue: asyncio.Queue = asyncio.Queue(64)
        self._task: asyncio.Task | None = None

    def start(self):
        self._task = asyncio.create_task(self._run())

    def stop(self):
        if self._task:
            self._task.cancel()

    async def send(self, msg: dict | str) -> None:
        await self.send_queue.put(msg)

    async def _run(self):
        try:
            reader, writer = await asyncio.open_connection(*_parse_addr(self._addr))
        except OSError as e:
            self._on_event("error", str(e))
            return

        self._on_event("connected", None)

        read_task = asyncio.create_task(self._read_one(reader))
        send_task = asyncio.create_task(self.send_queue.get())

        try:
            while True:
                done, _ = await asyncio.wait(
                    {read_task, send_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if read_task in done:
                    exc = read_task.exception()
                    if exc is not None:
                        self._on_event("disconnected", str(exc))
                        send_task.cancel()
                        return
                    msg = read_task.result()
                    if msg is None:
                        self._on_event("disconnected", "server closed connection")
                        send_task.cancel()
                        return
                    self._on_event("message", msg)
                    read_task = asyncio.create_task(self._read_one(reader))

                if send_task in done:
                    exc = send_task.exception()
                    if exc is not None:
                        send_task = asyncio.create_task(self.send_queue.get())
                        continue
                    outbound = send_task.result()
                    try:
                        await framing.write_frame(writer, codec.encode(outbound))
                    except Exception as e:
                        self._on_event("disconnected", f"write error: {e}")
                        read_task.cancel()
                        return
                    send_task = asyncio.create_task(self.send_queue.get())
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _read_one(self, reader: asyncio.StreamReader) -> dict | None:
        try:
            raw = await framing.read_frame(reader)
            return codec.decode(raw)
        except ProtocolError:
            raise
        except Exception as e:
            raise ProtocolError(str(e)) from e


def _parse_addr(addr: str) -> tuple[str, int]:
    if ":" in addr:
        host, port = addr.rsplit(":", 1)
        return host, int(port)
    return "127.0.0.1", int(addr)
