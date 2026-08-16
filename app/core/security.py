from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
import bcrypt


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

from app.core.config import settings






def create_access_token(user_id: int, token_type: str = "access") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),   # jose requires a string subject
        "typ": token_type,     # stops an invite token being replayed as a login token
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str = "access") -> int:
    """Return the user id encoded in the token, or raise JWTError."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("typ") != expected_type:
        raise JWTError("unexpected token type")
    return int(payload["sub"])