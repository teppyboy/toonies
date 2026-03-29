import struct
import pytest
import asyncio
import msgpack

from toonies_server.protocol.codec import encode, decode, make_server_message
from toonies_server.protocol.framing import read_frame, write_frame
from toonies_server.exceptions import ProtocolError


class TestCodec:
    def test_decode_unit_variant(self):
        raw = msgpack.packb("Ping", use_bin_type=True)
        msg = decode(raw)
        assert msg == {"type": "Ping"}

    def test_decode_struct_variant(self):
        raw = msgpack.packb({"Register": {"username": "alice", "password": "secret"}}, use_bin_type=True)
        msg = decode(raw)
        assert msg["type"] == "Register"
        assert msg["username"] == "alice"
        assert msg["password"] == "secret"

    def test_decode_login(self):
        raw = msgpack.packb({"Login": {"username": "bob", "password": "pass"}}, use_bin_type=True)
        msg = decode(raw)
        assert msg["type"] == "Login"

    def test_decode_chat_send(self):
        session_id = "550e8400-e29b-41d4-a716-446655440000"
        raw = msgpack.packb({"ChatSend": {"session_id": session_id, "content": "hello"}}, use_bin_type=True)
        msg = decode(raw)
        assert msg["type"] == "ChatSend"
        assert msg["session_id"] == session_id
        assert msg["content"] == "hello"

    def test_decode_invalid_bytes(self):
        with pytest.raises(ProtocolError):
            decode(b"\xff\xfe\xfd\xfc")

    def test_encode_unit_variant(self):
        msg = make_server_message("Pong")
        raw = encode(msg)
        decoded = msgpack.unpackb(raw, raw=False)
        assert decoded == "Pong"

    def test_encode_struct_variant(self):
        msg = make_server_message("RegisterResult", success=True, message="ok")
        raw = encode(msg)
        decoded = msgpack.unpackb(raw, raw=False)
        assert decoded == {"RegisterResult": {"success": True, "message": "ok"}}

    def test_encode_login_result(self):
        session_id = "550e8400-e29b-41d4-a716-446655440000"
        user_id = "660e8400-e29b-41d4-a716-446655440000"
        msg = make_server_message("LoginResult", success=True,
                                  session_id=session_id, user_id=user_id,
                                  message="Login successful")
        raw = encode(msg)
        decoded = msgpack.unpackb(raw, raw=False)
        assert decoded["LoginResult"]["success"] is True
        assert decoded["LoginResult"]["session_id"] == session_id


class TestFraming:
    async def test_round_trip(self):
        payload = b"hello world"
        port = _find_free_port()
        received = []

        async def handler(r, w):
            data = await read_frame(r)
            received.append(data)
            w.close()

        srv = await asyncio.start_server(handler, "127.0.0.1", port)
        async with srv:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            await write_frame(writer, payload)
            writer.close()
            await asyncio.sleep(0.05)

        assert received == [payload]

    async def test_write_then_read(self):
        # Use a pipe-like approach with asyncio streams
        server_ready = asyncio.Event()
        received = []

        async def server_handler(r, w):
            data = await read_frame(r)
            received.append(data)
            w.close()
            server_ready.set()

        port = _find_free_port()
        srv = await asyncio.start_server(server_handler, "127.0.0.1", port)
        async with srv:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            payload = b"test payload"
            await write_frame(writer, payload)
            writer.close()
            await server_ready.wait()

        assert received == [payload]

    async def test_max_payload_exact(self):
        from toonies_server.config import MAX_PAYLOAD_SIZE
        payload = b"x" * MAX_PAYLOAD_SIZE
        port = _find_free_port()
        received = []

        async def handler(r, w):
            data = await read_frame(r)
            received.append(data)
            w.close()

        srv = await asyncio.start_server(handler, "127.0.0.1", port)
        async with srv:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            await write_frame(writer, payload)
            writer.close()
            await asyncio.sleep(0.05)

        assert received == [payload]

    async def test_oversized_payload_rejected(self):
        from toonies_server.config import MAX_PAYLOAD_SIZE
        port = _find_free_port()

        async def handler(r, w):
            try:
                await read_frame(r)
            except ProtocolError:
                pass
            finally:
                w.close()

        srv = await asyncio.start_server(handler, "127.0.0.1", port)
        async with srv:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            # Manually send oversized header
            bad_length = MAX_PAYLOAD_SIZE + 1
            writer.write(struct.pack(">I", bad_length))
            writer.write(b"\x00" * bad_length)
            await writer.drain()
            writer.close()


def _find_free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _unused_port() -> int:
    return _find_free_port()
