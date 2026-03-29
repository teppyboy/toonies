from toonies_common.codec import encode, decode, make_message

# Server-specific alias: make_server_message → make_message
make_server_message = make_message

__all__ = ["encode", "decode", "make_message", "make_server_message"]
