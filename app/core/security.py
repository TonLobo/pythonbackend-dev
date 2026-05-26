from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from collections import defaultdict
import time
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_login_attempts: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(identifier: str) -> tuple[bool, int]:
    now = time.time()
    window = settings.LOCKOUT_MINUTES * 60
    _login_attempts[identifier] = [t for t in _login_attempts[identifier] if now - t < window]
    if len(_login_attempts[identifier]) >= settings.MAX_LOGIN_ATTEMPTS:
        wait = int(window - (now - _login_attempts[identifier][0]))
        return False, max(0, wait)
    return True, 0


def record_failed(identifier: str): _login_attempts[identifier].append(time.time())
def clear_attempts(identifier: str): _login_attempts.pop(identifier, None)
def hash_password(p: str) -> str: return pwd_context.hash(p)
def verify_password(plain: str, hashed: str) -> bool: return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = {**data, "exp": datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)), "type": "access"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    payload = {**data, "exp": datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "type": "refresh"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
