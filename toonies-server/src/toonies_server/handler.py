"""
Business logic: maps ClientMessage dicts to lists of ServerMessage dicts/strings.
Mirrors toonies-server/src/handler.rs process() function.
"""
import time
import uuid

import structlog

from toonies_server import auth
from toonies_server.protocol.codec import make_server_message
from toonies_server.state.models import UserRecord, Session
from toonies_server.state.store import AppState

logger = structlog.get_logger()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _validate_username(username: str) -> str | None:
    """Return None if valid, or an error message string."""
    if not username:
        return "username must not be empty"
    if len(username) > 32:
        return "username must be at most 32 characters"
    if not all(c.isalnum() or c == "_" for c in username):
        return "username must be alphanumeric or underscore"
    return None


async def process(msg: dict, state: AppState) -> list:
    match msg.get("type"):
        case "Register":
            return await _handle_register(msg, state)
        case "Login":
            return await _handle_login(msg, state)
        case "ChatSend":
            return await _handle_chat_send(msg, state)
        case "ListUsers":
            return _handle_list_users(msg, state)
        case "Disconnect":
            return await _handle_disconnect(msg, state)
        case "ChangePassword":
            return await _handle_change_password(msg, state)
        case "Ping":
            return ["Pong"]
        case _:
            logger.warning("unknown_message_type", type=msg.get("type"))
            return []


async def _handle_register(msg: dict, state: AppState) -> list:
    username = msg.get("username", "")
    password = msg.get("password", "")

    err = _validate_username(username)
    if err:
        return [make_server_message("RegisterResult", success=False, message=err)]

    async with state._lock:
        if username in state.users:
            return [make_server_message("RegisterResult", success=False, message="Username already taken")]

        password_hash = await auth.hash_password(password)
        user_id = str(uuid.uuid4())
        state.users[username] = UserRecord(user_id=user_id, username=username, password_hash=password_hash)

    logger.info("user_registered", username=username)
    return [make_server_message("RegisterResult", success=True, message="Registration successful")]


async def _handle_login(msg: dict, state: AppState) -> list:
    username = msg.get("username", "")
    password = msg.get("password", "")

    record = state.users.get(username)
    if record is None:
        return [make_server_message("LoginResult", success=False, session_id=None, user_id=None,
                                    message="Unknown username or wrong password")]

    ok = await auth.verify_password(password, record.password_hash)
    if not ok:
        return [make_server_message("LoginResult", success=False, session_id=None, user_id=None,
                                    message="Unknown username or wrong password")]

    session_id = str(uuid.uuid4())
    state.sessions[session_id] = Session(user_id=record.user_id, username=username)

    notice = make_server_message("SystemNotice", content=f"{username} joined", timestamp=_now_ms())
    await state.broadcast(notice)

    logger.info("user_logged_in", username=username, session_id=session_id)
    return [make_server_message("LoginResult", success=True, session_id=session_id,
                                user_id=record.user_id, message="Login successful")]


async def _handle_chat_send(msg: dict, state: AppState) -> list:
    session_id = msg.get("session_id", "")
    session = state.sessions.get(session_id)
    if session is None:
        logger.warning("chat_send_invalid_session", session_id=session_id)
        return []

    content = msg.get("content", "")
    broadcast_msg = make_server_message("ChatBroadcast", from_user=session.username,
                                        content=content, timestamp=_now_ms())
    await state.broadcast(broadcast_msg)
    return []


def _handle_list_users(msg: dict, state: AppState) -> list:
    session_id = msg.get("session_id", "")
    if session_id not in state.sessions:
        logger.warning("list_users_invalid_session", session_id=session_id)
        return []

    users = [s.username for s in state.sessions.values()]
    return [make_server_message("UserList", users=users)]


async def _handle_disconnect(msg: dict, state: AppState) -> list:
    session_id = msg.get("session_id", "")
    session = state.sessions.pop(session_id, None)
    if session is not None:
        notice = make_server_message("SystemNotice", content=f"{session.username} left", timestamp=_now_ms())
        await state.broadcast(notice)
        logger.info("user_disconnected", username=session.username)
    return []


async def _handle_change_password(msg: dict, state: AppState) -> list:
    session_id = msg.get("session_id", "")
    session = state.sessions.get(session_id)
    if session is None:
        logger.warning("change_password_invalid_session", session_id=session_id)
        return [make_server_message("ChangePasswordResult", success=False, message="Not authenticated")]

    username = session.username
    record = state.users.get(username)
    if record is None:
        return [make_server_message("ChangePasswordResult", success=False, message="User record not found")]

    old_password = msg.get("old_password", "")
    new_password = msg.get("new_password", "")

    ok = await auth.verify_password(old_password, record.password_hash)
    if not ok:
        return [make_server_message("ChangePasswordResult", success=False, message="Old password is incorrect")]

    new_hash = await auth.hash_password(new_password)
    record.password_hash = new_hash

    logger.info("password_changed", username=username)
    return [make_server_message("ChangePasswordResult", success=True, message="Password changed successfully")]
