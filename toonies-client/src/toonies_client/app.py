"""
Textual TUI application — Minecraft-style chat client.
Mirrors toonies-client/src/{app,ui,event,command}.rs.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.suggester import Suggester
from textual.widgets import Input, RichLog, Static

from toonies_client import command as cmd
from toonies_client.network import NetworkWorker
from toonies_common.codec import make_message
from toonies_common.config import DEFAULT_HOST, DEFAULT_PORT


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

@dataclass
class Session:
    session_id: str
    user_id: str
    username: str


# ---------------------------------------------------------------------------
# Textual messages (for thread-safe cross-task communication)
# ---------------------------------------------------------------------------

class NetConnected(Message):
    pass


class NetMessage(Message):
    def __init__(self, msg: dict) -> None:
        super().__init__()
        self.msg = msg


class NetDisconnected(Message):
    def __init__(self, reason: str) -> None:
        super().__init__()
        self.reason = reason


class NetError(Message):
    def __init__(self, error: str) -> None:
        super().__init__()
        self.error = error


# ---------------------------------------------------------------------------
# Autosuggester
# ---------------------------------------------------------------------------

class CommandSuggester(Suggester):
    async def get_suggestion(self, value: str) -> str | None:
        suffix = cmd.suggestion(value)
        if suffix is None:
            return None
        return value + suffix


# ---------------------------------------------------------------------------
# Input widget with command history
# ---------------------------------------------------------------------------

class ChatInput(Input):
    """Input widget that adds Up/Down history navigation."""

    BINDINGS: ClassVar = [
        Binding("up", "history_prev", show=False, priority=True),
        Binding("down", "history_next", show=False, priority=True),
        Binding("tab", "suggest", show=False, priority=True),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._history: list[str] = []
        self._history_pos: int | None = None
        self._history_draft: str = ""

    def push_history(self, line: str) -> None:
        if line and (not self._history or self._history[-1] != line):
            self._history.append(line)
        self._history_pos = None
        self._history_draft = ""

    def action_suggest(self) -> None:
        if self._suggestion:
            self.value = self._suggestion
            self.cursor_position = len(self.value)

    def action_history_prev(self) -> None:
        if not self._history:
            return
        if self._history_pos is None:
            self._history_draft = self.value
            self._history_pos = len(self._history) - 1
        elif self._history_pos > 0:
            self._history_pos -= 1
        self.value = self._history[self._history_pos]
        self.cursor_position = len(self.value)

    def action_history_next(self) -> None:
        if self._history_pos is None:
            return
        if self._history_pos + 1 >= len(self._history):
            self._history_pos = None
            self.value = self._history_draft
        else:
            self._history_pos += 1
            self.value = self._history[self._history_pos]
        self.cursor_position = len(self.value)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class TooniesApp(App):
    CSS = """
    Screen {
        layout: vertical;
        background: #1a1a2e;
    }

    #title {
        height: 1;
        background: #16213e;
        color: #e2b96f;
        text-align: center;
        text-style: bold;
    }

    #messages {
        height: 1fr;
        border: solid #0f3460;
        scrollbar-color: #0f3460;
        padding: 0 1;
    }

    #status {
        height: 1;
        background: #0f3460;
        color: #a8dadc;
        padding: 0 1;
    }

    #input {
        height: 3;
        border: solid #0f3460;
        background: #16213e;
        color: #e0e0e0;
    }

    #input:focus {
        border: solid #e2b96f;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit_double", show=False, priority=True),
        Binding("escape", "quit", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.server_addr = f"{DEFAULT_HOST}:{DEFAULT_PORT}"
        self.session: Session | None = None
        self.pending_login: str | None = None
        self._ctrl_c_pending = False
        self._net: NetworkWorker | None = None

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static("  toonies  ", id="title")
        yield RichLog(id="messages", highlight=True, markup=True, wrap=True)
        yield Static(self._status_text(), id="status")
        yield ChatInput(
            placeholder="Type a message or /help for commands",
            suggester=CommandSuggester(use_cache=False),
            id="input",
        )

    def on_mount(self) -> None:
        self.query_one("#input").focus()
        self._push_system("Welcome to toonies! Type /help for commands.")
        self._push_system(f"Default server: {self.server_addr}  — use /set-server <host:port> to change.")
        self._connect()

    # ------------------------------------------------------------------
    # Status bar helpers
    # ------------------------------------------------------------------

    def _status_text(self) -> str:
        if self.session:
            return f"● Connected  |  {self.session.username}  |  {self.server_addr}"
        if self._net is None:
            return f"○ Disconnected  |  {self.server_addr}"
        return f"◌ Connecting…  |  {self.server_addr}"

    def _refresh_status(self) -> None:
        self.query_one("#status", Static).update(self._status_text())

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ts() -> str:
        t = time.localtime()
        return f"{t.tm_hour:02}:{t.tm_min:02}:{t.tm_sec:02}"

    def _push_chat(self, username: str, content: str) -> None:
        log = self.query_one("#messages", RichLog)
        log.write(f"[dim]{self._ts()}[/dim] [bold white]<{username}>[/bold white] {content}")

    def _push_system(self, content: str) -> None:
        log = self.query_one("#messages", RichLog)
        log.write(f"[dim]{self._ts()}[/dim] [yellow]*** {content}[/yellow]")

    def _push_error(self, content: str) -> None:
        log = self.query_one("#messages", RichLog)
        log.write(f"[dim]{self._ts()}[/dim] [bold red]! {content}[/bold red]")

    def _push_info(self, content: str) -> None:
        log = self.query_one("#messages", RichLog)
        log.write(f"[dim]{self._ts()}[/dim] [cyan]{content}[/cyan]")

    # ------------------------------------------------------------------
    # Networking
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        if self._net:
            self._net.stop()
        worker = NetworkWorker(self.server_addr, self._net_event_callback)
        self._net = worker
        worker.start()
        self._refresh_status()

    def _net_event_callback(self, event_type: str, data) -> None:
        """Called from the network task; post a Textual message to be handled on the main loop."""
        if event_type == "connected":
            self.post_message(NetConnected())
        elif event_type == "message":
            self.post_message(NetMessage(data))
        elif event_type == "disconnected":
            self.post_message(NetDisconnected(data or "unknown reason"))
        elif event_type == "error":
            self.post_message(NetError(data or "unknown error"))

    # ------------------------------------------------------------------
    # Network event handlers
    # ------------------------------------------------------------------

    def on_net_connected(self, _: NetConnected) -> None:
        self._push_system(f"Connected to {self.server_addr}.")
        self._refresh_status()

    def on_net_disconnected(self, event: NetDisconnected) -> None:
        self._push_error(f"Disconnected: {event.reason}")
        self.session = None
        self._net = None
        self._refresh_status()

    def on_net_error(self, event: NetError) -> None:
        self._push_error(f"Connection error: {event.error}")
        self._net = None
        self._refresh_status()

    def on_net_message(self, event: NetMessage) -> None:
        self._dispatch_server_message(event.msg)

    def _dispatch_server_message(self, msg: dict) -> None:
        match msg.get("type"):
            case "ChatBroadcast":
                self._push_chat(msg.get("from_user", "?"), msg.get("content", ""))
            case "RegisterResult":
                if msg.get("success"):
                    self._push_system(f"Registered: {msg.get('message', '')}")
                else:
                    self._push_error(f"Registration failed: {msg.get('message', '')}")
            case "LoginResult":
                if msg.get("success"):
                    sid = msg.get("session_id")
                    uid = msg.get("user_id")
                    username = self.pending_login or "unknown"
                    self.pending_login = None
                    self.session = Session(session_id=sid, user_id=uid, username=username)
                    self._push_system(f"Logged in as {username}.")
                else:
                    self.pending_login = None
                    self._push_error(f"Login failed: {msg.get('message', '')}")
                self._refresh_status()
            case "UserList":
                users = msg.get("users", [])
                self._push_info(f"Online ({len(users)} user(s)): {', '.join(users)}")
            case "SystemNotice":
                self._push_system(msg.get("content", ""))
            case "ChangePasswordResult":
                if msg.get("success"):
                    self._push_system(f"Password changed: {msg.get('message', '')}")
                else:
                    self._push_error(f"Password change failed: {msg.get('message', '')}")
            case "Pong":
                pass
            case "ServerShutdown":
                self._push_error(f"Server shutting down: {msg.get('message', '')}")
                self.session = None
                self._net = None
                self._refresh_status()

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    @on(Input.Submitted, "#input")
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        line = event.value.strip()
        input_widget = self.query_one("#input", ChatInput)
        input_widget.clear()
        input_widget.push_history(line)
        self._ctrl_c_pending = False

        if not line:
            return

        if line.startswith("/"):
            await self._execute_command(line)
        else:
            if self.session is None:
                self._push_error("Not logged in. Use /login <username> <password>.")
                return
            if self._net:
                await self._net.send(make_message(
                    "ChatSend",
                    session_id=self.session.session_id,
                    content=line,
                ))

    async def _execute_command(self, line: str) -> None:
        command, arg1, arg2 = cmd.parse(line)

        match command:
            case "/help":
                for l in cmd.HELP_LINES:
                    self._push_info(l)

            case "/exit" | "/quit":
                self.exit()

            case "/set-server":
                if not arg1:
                    self._push_error("Usage: /set-server <host:port>")
                    return
                self.server_addr = arg1
                self.session = None
                self._push_system(f"Connecting to {arg1}…")
                self._connect()

            case "/register":
                if self.session:
                    self._push_error("Already logged in. Use /logout before registering.")
                    return
                if not arg1 or not arg2:
                    self._push_error("Usage: /register <username> <password>")
                    return
                if not self._net:
                    self._push_error("Not connected. Use /set-server <addr> first.")
                    return
                await self._net.send(make_message("Register", username=arg1, password=arg2))

            case "/login":
                if not arg1 or not arg2:
                    self._push_error("Usage: /login <username> <password>")
                    return
                if not self._net:
                    self._push_error("Not connected. Use /set-server <addr> first.")
                    return
                self.pending_login = arg1
                await self._net.send(make_message("Login", username=arg1, password=arg2))

            case "/logout":
                if not self.session:
                    self._push_error("Not logged in.")
                    return
                if self._net:
                    await self._net.send(make_message("Disconnect", session_id=self.session.session_id))
                self.session = None
                self._push_system("Logged out.")
                self._refresh_status()

            case "/passwd":
                if not arg1 or not arg2:
                    self._push_error("Usage: /passwd <old_password> <new_password>")
                    return
                if not self.session:
                    self._push_error("Not logged in.")
                    return
                if self._net:
                    await self._net.send(make_message(
                        "ChangePassword",
                        session_id=self.session.session_id,
                        old_password=arg1,
                        new_password=arg2,
                    ))

            case "/users":
                if not self.session:
                    self._push_error("Not logged in.")
                    return
                if self._net:
                    await self._net.send(make_message("ListUsers", session_id=self.session.session_id))

            case _:
                self._push_error(f"Unknown command: {command}. Type /help for available commands.")

    # ------------------------------------------------------------------
    # Quit actions
    # ------------------------------------------------------------------

    def action_quit_double(self) -> None:
        if self._ctrl_c_pending:
            self.exit()
        else:
            self._ctrl_c_pending = True
            self._push_info("Press Ctrl+C again to exit, or type /quit")

    def action_quit(self) -> None:
        self.exit()
