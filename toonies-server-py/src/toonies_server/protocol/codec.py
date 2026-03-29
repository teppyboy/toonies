"""
MessagePack codec compatible with rmp_serde::to_vec_named (Rust).

Rust serde external tagging format:
  Unit variant:   "Ping"
  Struct variant: {"Register": {"username": "alice", "password": "x"}}

UUID is serialized as lowercase hyphenated string by the uuid crate.
Username newtype is transparent (plain string).
"""
import msgpack

from toonies_server.exceptions import ProtocolError


def encode(msg: dict | str) -> bytes:
    """Encode a server message to msgpack bytes (rmp_serde named format)."""
    return msgpack.packb(msg, use_bin_type=True)


def decode(raw: bytes) -> dict:
    """Decode a client message from msgpack bytes (rmp_serde named format).

    Returns a normalized dict with a ``"type"`` key and the variant fields
    merged at the top level.
    """
    try:
        data = msgpack.unpackb(raw, raw=False)
    except Exception as e:
        raise ProtocolError(f"msgpack decode failed: {e}") from e

    if isinstance(data, str):
        # Unit variant: "Ping"
        return {"type": data}

    if isinstance(data, dict):
        if len(data) != 1:
            raise ProtocolError(f"expected single-key dict, got {len(data)} keys")
        variant, fields = next(iter(data.items()))
        if isinstance(fields, dict):
            return {"type": variant, **fields}
        # Scalar payload (shouldn't occur in current protocol)
        return {"type": variant, "value": fields}

    raise ProtocolError(f"unexpected msgpack top-level type: {type(data).__name__}")


def make_server_message(variant: str, **fields) -> dict | str:
    """Build the wire-format dict/string for a ServerMessage variant."""
    if not fields:
        return variant  # unit variant → plain string
    return {variant: fields}
