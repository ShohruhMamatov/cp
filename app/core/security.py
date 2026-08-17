from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings


def hash_password(password: str) -> str:
    # bcrypt operates on bytes and hard-caps at 72; encode first, because
    # len(str) != len(bytes) for non-ASCII passwords.
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        # malformed hash in the DB — treat as a failed login, not a 500
        return False


def create_access_token(user_id: int, token_type: str = "access") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "typ": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str = "access") -> int:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("typ") != expected_type:
        raise InvalidTokenError("unexpected token type")
    return int(payload["sub"])
