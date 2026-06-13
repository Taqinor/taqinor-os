import os
from jose import JWTError, jwt
from datetime import datetime, timedelta
import bcrypt

# The JWT signing secret is provided ONLY at runtime, server-side (the systemd
# unit loads it from /opt/taqinor-simulator/secret.env via EnvironmentFile).
# It is never hardcoded or committed. Fail closed if it is missing.
SECRET_KEY = os.environ.get("SIMULATOR_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SIMULATOR_SECRET_KEY is not set. Configure it server-side "
        "(EnvironmentFile in the systemd unit) — never hardcode it."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns payload dict or None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
