# toonies

A real-time terminal chat application built in Rust. Client-server architecture with a TUI frontend, user authentication, and binary MessagePack protocol.

## Project Structure

| Crate | Description |
|---|---|
| `toonies-common` | Shared protocol types, message definitions, error handling |
| `toonies-server` | TCP/UDP server with auth, session management, message routing |
| `toonies-client` | TUI client built with ratatui + crossterm |

## Features

- User registration and login with Argon2 password hashing
- Real-time broadcast chat with system notifications
- Slash commands with tab-completion and history
- Length-prefixed MessagePack wire protocol over TCP
- Graceful shutdown with Ctrl+C

## Build

```bash
cargo build --release
```

## Run

```bash
# Start server (default: 0.0.0.0:7878)
cargo run -p toonies-server

# Start client
cargo run -p toonies-client
```

## Client Commands

| Command | Description |
|---|---|
| `/register <user> <pass>` | Create an account |
| `/login <user> <pass>` | Log in |
| `/users` | List online users |
| `/passwd <old> <new>` | Change password |
| `/set-server <addr>` | Change server address |
| `/help` | Show all commands |
| `/quit` | Exit |

## Configuration

- **Server**: Custom address via CLI argument — `cargo run -p toonies-server 127.0.0.1:9999`
- **Client**: Default connects to `127.0.0.1:7878`, changeable via `/set-server`
- **Logging**: Server uses `RUST_LOG` env var; client logs to `toonies-client.log`

## License

[MIT](./LICENSE)
