import pytest
from toonies_server.handler import process
from toonies_server.state.store import AppState
from toonies_server.state.models import UserRecord, Session


async def test_ping(state):
    result = await process({"type": "Ping"}, state)
    assert result == ["Pong"]


async def test_register_success(state):
    result = await process({"type": "Register", "username": "alice", "password": "pass123"}, state)
    assert len(result) == 1
    assert result[0]["RegisterResult"]["success"] is True
    assert "alice" in state.users


async def test_register_duplicate(state):
    await process({"type": "Register", "username": "alice", "password": "pass"}, state)
    result = await process({"type": "Register", "username": "alice", "password": "other"}, state)
    assert result[0]["RegisterResult"]["success"] is False
    assert "already taken" in result[0]["RegisterResult"]["message"]


async def test_register_invalid_username(state):
    result = await process({"type": "Register", "username": "alice bob", "password": "pass"}, state)
    assert result[0]["RegisterResult"]["success"] is False


async def test_login_success(state):
    await process({"type": "Register", "username": "alice", "password": "pass123"}, state)
    result = await process({"type": "Login", "username": "alice", "password": "pass123"}, state)
    assert result[0]["LoginResult"]["success"] is True
    session_id = result[0]["LoginResult"]["session_id"]
    assert session_id in state.sessions


async def test_login_wrong_password(state):
    await process({"type": "Register", "username": "alice", "password": "correct"}, state)
    result = await process({"type": "Login", "username": "alice", "password": "wrong"}, state)
    assert result[0]["LoginResult"]["success"] is False


async def test_login_unknown_user(state):
    result = await process({"type": "Login", "username": "nobody", "password": "x"}, state)
    assert result[0]["LoginResult"]["success"] is False


async def test_chat_send_valid_session(state):
    await process({"type": "Register", "username": "alice", "password": "pass"}, state)
    login = await process({"type": "Login", "username": "alice", "password": "pass"}, state)
    session_id = login[0]["LoginResult"]["session_id"]

    q = state.subscribe()
    # Skip the "alice joined" system notice already in queue
    state.unsubscribe(q)
    q2 = state.subscribe()

    result = await process({"type": "ChatSend", "session_id": session_id, "content": "hello"}, state)
    assert result == []

    broadcast = q2.get_nowait()
    assert broadcast["ChatBroadcast"]["from_user"] == "alice"
    assert broadcast["ChatBroadcast"]["content"] == "hello"
    state.unsubscribe(q2)


async def test_chat_send_invalid_session(state):
    result = await process({"type": "ChatSend", "session_id": "bad-uuid", "content": "hi"}, state)
    assert result == []


async def test_list_users(state):
    await process({"type": "Register", "username": "alice", "password": "pass"}, state)
    login = await process({"type": "Login", "username": "alice", "password": "pass"}, state)
    session_id = login[0]["LoginResult"]["session_id"]

    result = await process({"type": "ListUsers", "session_id": session_id}, state)
    users = result[0]["UserList"]["users"]
    assert "alice" in users


async def test_disconnect(state):
    await process({"type": "Register", "username": "alice", "password": "pass"}, state)
    login = await process({"type": "Login", "username": "alice", "password": "pass"}, state)
    session_id = login[0]["LoginResult"]["session_id"]

    assert session_id in state.sessions
    await process({"type": "Disconnect", "session_id": session_id}, state)
    assert session_id not in state.sessions


async def test_change_password(state):
    await process({"type": "Register", "username": "alice", "password": "oldpass"}, state)
    login = await process({"type": "Login", "username": "alice", "password": "oldpass"}, state)
    session_id = login[0]["LoginResult"]["session_id"]

    result = await process({
        "type": "ChangePassword",
        "session_id": session_id,
        "old_password": "oldpass",
        "new_password": "newpass",
    }, state)
    assert result[0]["ChangePasswordResult"]["success"] is True

    # Can login with new password
    login2 = await process({"type": "Login", "username": "alice", "password": "newpass"}, state)
    assert login2[0]["LoginResult"]["success"] is True


async def test_change_password_wrong_old(state):
    await process({"type": "Register", "username": "alice", "password": "correct"}, state)
    login = await process({"type": "Login", "username": "alice", "password": "correct"}, state)
    session_id = login[0]["LoginResult"]["session_id"]

    result = await process({
        "type": "ChangePassword",
        "session_id": session_id,
        "old_password": "wrong",
        "new_password": "new",
    }, state)
    assert result[0]["ChangePasswordResult"]["success"] is False


async def test_unknown_message(state):
    result = await process({"type": "Unknown"}, state)
    assert result == []
