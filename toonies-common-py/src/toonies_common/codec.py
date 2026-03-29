"""
MessagePack codec compatible with rmp_serde::to_vec_named (Rust).

Wire format (serde external tagging):
  Unit variant:   "Ping"
  Struct variant: {"Register": {"username": "alice", "password": "x"}}

UUID → lowercase hyphenated string.
Username newtype → plain string.
"""
import msgpack

from toonies_common.exceptions import ProtocolError


def encode(msg: dict | str) -> bytes:
    """Encode a message to msgpack bytes."""
    return msgpack.packb(msg, use_bin_type=True)


def decode(raw: bytes) -> dict:
    """Decode a message from msgpack bytes.

    Returns a normalized dict with a ``"type"`` key plus variant fields
    merged at the top level.
    """
    try:
        data = msgpack.unpackb(raw, raw=False)
    except Exception as e:
        raise ProtocolError(f"msgpack decode failed: {e}") from e

    if isinstance(data, str):
        return {"type": data}

    if isinstance(data, dict):
        if len(data) != 1:
            raise ProtocolError(f"expected single-key dict, got {len(data)} keys")
        variant, fields = next(iter(data.items()))
        if isinstance(fields, dict):
            return {"type": variant, **fields}
        return {"type": variant, "value": fields}

    raise ProtocolError(f"unexpected msgpack top-level type: {type(data).__name__}")


def make_message(variant: str, **fields) -> dict | str:
    """Build the wire-format value for a message variant."""
    if not fields:
        return variant
    return {variant: fields}
