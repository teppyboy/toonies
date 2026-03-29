"""
Password hashing and verification using argon2-cffi.

All CPU-bound argon2 operations are offloaded via asyncio.to_thread()
to avoid blocking the event loop (~200-500 ms per operation).
"""
import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

_ph = PasswordHasher()


def _hash_sync(password: str) -> str:
    return _ph.hash(password)


def _verify_sync(password: str, hash_: str) -> bool:
    try:
        return _ph.verify(hash_, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hash_sync, password)


async def verify_password(password: str, hash_: str) -> bool:
    return await asyncio.to_thread(_verify_sync, password, hash_)
