"""
Command parsing and autosuggestion.
Mirrors toonies-client/src/command.rs.
"""

COMMANDS: list[str] = sorted([
    "/exit",
    "/help",
    "/login",
    "/logout",
    "/passwd",
    "/quit",
    "/register",
    "/set-server",
    "/users",
])

HELP_LINES = [
    "Available commands:",
    "  /register <username> <password>  - create account",
    "  /login <username> <password>     - log in",
    "  /logout                          - log out",
    "  /passwd <old> <new>              - change password",
    "  /set-server <host:port>          - set server address",
    "  /users                           - list online users",
    "  /exit or /quit                   - exit",
]


def suggestion(input_text: str) -> str | None:
    """Return ghost-text suffix for the first matching command, or None."""
    if not input_text.startswith("/") or " " in input_text:
        return None
    for cmd in COMMANDS:
        if cmd.startswith(input_text) and cmd != input_text:
            return cmd[len(input_text):]
    return None


def parse(line: str) -> tuple[str, str | None, str | None]:
    """Split 'cmd arg1 rest' into (cmd, arg1, rest). All may be empty/None."""
    parts = line.split(" ", 2)
    cmd = parts[0]
    arg1 = parts[1] if len(parts) > 1 else None
    arg2 = parts[2] if len(parts) > 2 else None
    return cmd, arg1, arg2
