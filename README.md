# toonies

A real-time terminal chat application written in Python. Client-server architecture with a TUI frontend, user authentication, and binary MessagePack protocol.

## Project Structure

| Package | Description |
|---|---|
| `toonies-common` | Shared protocol: MessagePack codec, framing, config, exceptions |
| `toonies-server` | asyncio TCP server with Argon2 auth, session management, broadcast |
| `toonies-client` | Textual TUI client with slash commands, history, and autosuggestion |

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Install

```bash
uv sync
```

## Run

```bash
# Start server (default: 0.0.0.0:7878)
uv run toonies-server

# Custom address
uv run toonies-server 0.0.0.0:9999

# Start client
uv run toonies
```

## Test

```bash
uv run pytest
```

## Client Commands

| Command | Description |
|---|---|
| `/register <user> <pass>` | Create an account |
| `/login <user> <pass>` | Log in |
| `/logout` | Log out |
| `/users` | List online users |
| `/passwd <old> <new>` | Change password |
| `/set-server <host:port>` | Change server address and reconnect |
| `/help` | Show all commands |
| `/exit` or `/quit` | Exit |

## Client Shortcuts

| Key | Action |
|---|---|
| `Tab` | Accept command autosuggestion |
| `Up` / `Down` | Browse input history |
| `Ctrl+C` twice | Exit |
| `Escape` | Exit |

## Protocol

Length-prefixed MessagePack over TCP (4-byte big-endian length + payload, max 64 KiB), wire-compatible with the original Rust implementation.

## Legacy

The original Rust implementation (ratatui client, tokio server) is preserved on the [`legacy/rust`](../../tree/legacy/rust) branch.

## License

[MIT](./LICENSE)
