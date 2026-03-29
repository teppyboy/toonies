import pytest
from toonies_server.auth import hash_password, verify_password


async def test_hash_and_verify():
    h = await hash_password("correcthorsebatterystaple")
    assert await verify_password("correcthorsebatterystaple", h) is True


async def test_wrong_password():
    h = await hash_password("mypassword")
    assert await verify_password("wrongpassword", h) is False


async def test_empty_password():
    h = await hash_password("")
    assert await verify_password("", h) is True
    assert await verify_password("x", h) is False


async def test_hash_is_different_each_call():
    h1 = await hash_password("same")
    h2 = await hash_password("same")
    assert h1 != h2  # different salts
    assert await verify_password("same", h1) is True
    assert await verify_password("same", h2) is True
