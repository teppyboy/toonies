import asyncio
import struct

from toonies_common.config import MAX_PAYLOAD_SIZE
from toonies_common.exceptions import ProtocolError


async def read_frame(reader: asyncio.StreamReader) -> bytes:
    try:
        header = await reader.readexactly(4)
    except asyncio.IncompleteReadError as e:
        raise ProtocolError("connection closed while reading header") from e

    (length,) = struct.unpack(">I", header)
    if length > MAX_PAYLOAD_SIZE:
        raise ProtocolError(f"payload {length} exceeds max {MAX_PAYLOAD_SIZE}")

    try:
        return await reader.readexactly(length)
    except asyncio.IncompleteReadError as e:
        raise ProtocolError("connection closed while reading payload") from e


async def write_frame(writer: asyncio.StreamWriter, payload: bytes) -> None:
    if len(payload) > MAX_PAYLOAD_SIZE:
        raise ProtocolError(f"payload {len(payload)} exceeds max {MAX_PAYLOAD_SIZE}")
    writer.write(struct.pack(">I", len(payload)) + payload)
    await writer.drain()
