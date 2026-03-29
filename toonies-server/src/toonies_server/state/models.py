from dataclasses import dataclass


@dataclass
class UserRecord:
    user_id: str       # UUID string
    username: str
    password_hash: str  # argon2 PHC string


@dataclass
class Session:
    user_id: str
    username: str
