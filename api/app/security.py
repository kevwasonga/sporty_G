import datetime as dt
import hashlib
import hmac
import logging
import secrets
import string

from cryptography.fernet import Fernet, InvalidToken

from .config import settings

logger = logging.getLogger("sporty.lab")


class Status:
    PENDING = "pending"
    SENDING = "sending"
    OTP_SENT = "otp_sent"
    OTP_VERIFIED = "otp_verified"
    FAILED = "failed"

    DECISIONS = (PENDING, SENDING, OTP_SENT, OTP_VERIFIED, FAILED)


def normalize_phone(raw: str) -> str:
    """Keep only digits; default to international format without '+'."""
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    return digits


def generate_password(length: int | None = None) -> str:
    """CSPRNG password with at least one lower, upper, digit and symbol."""
    length = length or settings.password_length
    if length < 8:
        length = 8

    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    symbols = "!@#$%^&*()-_=+[]{};:,.<>?"

    pool = lower + upper + digits + symbols
    pw = [
        secrets.choice(lower),
        secrets.choice(upper),
        secrets.choice(digits),
        secrets.choice(symbols),
    ]
    pw += [secrets.choice(pool) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(pw)
    return "".join(pw)


def generate_otp(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def hash_otp(otp: str) -> str:
    return hashlib.blake2b(otp.encode(), salt=b"sportyotp").hexdigest()


def check_otp(otp: str, digest: str | None) -> bool:
    if not digest:
        return False
    return hmac.compare_digest(hash_otp(otp), digest)


# ---------------------------------------------------------------------------
# Fernet encryption at rest (passwords / OTP secrets)
# ---------------------------------------------------------------------------

_fernet: Fernet | None = None


def _fernet_instance() -> Fernet | None:
    global _fernet
    if _fernet is not None:
        return _fernet
    if not settings.encrypt_key:
        return None
    try:
        _fernet = Fernet(settings.encrypt_key.encode())
    except Exception as exc:  # pragma: no cover - config error path
        logger.warning("Invalid ENCRYPT_KEY; falling back to plaintext storage: %s", exc)
        _fernet = None
    return _fernet


def encrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    f = _fernet_instance()
    if f is None:
        return value
    return f.encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    f = _fernet_instance()
    if f is None:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except InvalidToken:  # pragma: no cover - corrupt data path
        logger.warning("Failed to decrypt a secret (key rotated?); returning raw.")
        return value


def otp_valid_window(created_at: dt.datetime | None, now: dt.datetime | None = None) -> bool:
    if created_at is None:
        return False
    now = now or dt.datetime.now(dt.timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=dt.timezone.utc)
    return created_at >= now - dt.timedelta(seconds=settings.otp_ttl_seconds)