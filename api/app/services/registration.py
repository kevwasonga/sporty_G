"""Business logic: everything that is independent of the OTP provider."""

import datetime as dt
import logging
import threading

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..config import settings
from ..database import SessionLocal
from ..models import Registration
from ..providers.base import ProviderAdapter, SendContext
from ..security import (
    Status,
    check_otp,
    decrypt_secret,
    encrypt_secret,
    generate_password,
    normalize_phone,
    otp_valid_window,
)
from .imports import parse_contacts

logger = logging.getLogger("sporty.services")

MAX_OTP_ATTEMPTS = 5
PHONE_MIN_DIGITS = 7
PHONE_MAX_DIGITS = 15

# Supported countries (dial codes the product supports; changing this list is
# the single source of truth for which numbers can be registered).
SUPPORTED_COUNTRIES = {"234": "Nigeria", "254": "Kenya"}


def supported_country_for(phone: str) -> str | None:
    for code, country in SUPPORTED_COUNTRIES.items():
        if phone.startswith(code):
            return country
    return None


def _decrypt_row_password(row: Registration) -> str | None:
    return decrypt_secret(row.password)


def _row_out(row: Registration) -> schemas.RegistrationOut:
    return schemas.to_registration_out(
        row,
        password=_decrypt_row_password(row),
    )


def create_registration(
    db: Session,
    phone: str,
    password: str | None,
    manual_sms_select: bool = False,
) -> schemas.RegistrationOut:
    """Create a registration: normalize phone, generate/store password, persist.

    A generated password IS returned in cleartext so the operator can email the
    client. Only Nigeria (+234) and Kenya (+254) numbers are accepted.
    """
    clean = normalize_phone(phone)
    if not (PHONE_MIN_DIGITS <= len(clean) <= PHONE_MAX_DIGITS):
        raise HTTPException(
            status_code=422,
            detail=f"Phone number must contain {PHONE_MIN_DIGITS}-{PHONE_MAX_DIGITS} digits.",
        )
    country = supported_country_for(clean)
    if country is None:
        raise HTTPException(
            status_code=422,
            detail="Only Nigeria (+234) and Kenya (+254) numbers are supported.",
        )

    existing = db.scalar(select(Registration).where(Registration.phone == clean))
    if existing is not None:
        raise HTTPException(status_code=409, detail="This phone number is already registered.")

    secret = password.strip() if (password or "").strip() else generate_password()
    if not (8 <= len(secret) <= 128):
        raise HTTPException(
            status_code=422,
            detail="Password must be 8-128 characters (SportyBet requires at least 8).",
        )

    row = Registration(
        phone=clean,
        password=encrypt_secret(secret),
        status=Status.PENDING,
        provider=settings.provider.lower(),
        manual_sms_select=manual_sms_select,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    logger.info("Registration created for %s (%s)", clean, country)
    return _row_out(row)


def request_send_otp(db: Session, reg: Registration) -> schemas.SendOtpResponse:
    """Mark the row 'sending' and hand the real delivery to a background worker.

    Returns immediately so the UI can show a spinner while the provider does its
    paced, human-like work (browser fill, OTP request, 30-60s delivery wait).
    FAILED rows may be re-sent -> the queue can cool down, retry, then re-queue.
    """
    if reg.status not in (Status.PENDING, Status.SENDING, Status.FAILED):
        return schemas.SendOtpResponse(
            id=reg.id, phone=reg.phone, status=reg.status,
            message="No OTP is outstanding for this number.",
        )

    reg.status = Status.SENDING
    reg.error = None
    db.commit()

    threading.Thread(target=_deliver_otp, args=(reg.id,), daemon=True).start()

    return schemas.SendOtpResponse(
        id=reg.id,
        phone=reg.phone,
        status=Status.SENDING,
        provider_ref=reg.provider_ref,
        message="OTP request started. SportyBet registers the number and texts the code to the phone.",
    )


def _deliver_otp(reg_id: int) -> None:
    """Background worker: run the provider, then flip status to otp_sent/failed.

    Runs in its own session because SQLAlchemy sessions are not thread-safe.
    """
    from ..providers import get_provider

    db = SessionLocal()
    try:
        reg = db.get(Registration, reg_id)
        if reg is None or reg.status != Status.SENDING:
            return

        provider = get_provider(reg.provider)
        password = _decrypt_row_password(reg)
        if not password:
            reg.status = Status.FAILED
            reg.error = "No password stored for this registration."
            db.commit()
            return

        try:
            result = provider.send_otp(
                SendContext(
                    phone=reg.phone,
                    password=password,
                    manual_sms_select=bool(reg.manual_sms_select),
                )
            )
        except Exception as exc:
            logger.exception("Provider failure for %s", reg.phone)
            reg.status = Status.FAILED
            reg.error = str(exc)[:500]
            db.commit()
            return

        if not result.success:
            reason = (result.message or "").strip()
            detail = (result.error or "").strip()
            reg.error = (
                f"{reason} ({detail})"
                if detail and detail not in reason
                else (reason or detail or "OTP delivery failed.")
            )
            reg.status = Status.FAILED
            db.commit()
            return

        now = dt.datetime.now(dt.timezone.utc)
        # SportyBet validates the OTP it sends via SMS itself; a local hash is
        # never stored for a real platform (test fakes may set one directly).
        reg.otp_hash = None
        reg.otp_sent_at = now
        reg.otp_attempts = 0
        reg.status = Status.OTP_SENT
        reg.provider_ref = result.provider_ref
        reg.error = None
        db.commit()
        logger.info("OTP delivered for %s via %s", reg.phone, provider.name)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Background OTP delivery crashed for reg %d", reg_id)
        try:
            stale = db.get(Registration, reg_id)
            if stale:
                stale.status = Status.FAILED
                stale.error = str(exc)[:500]
                db.commit()
        except Exception:  # pragma: no cover
            db.rollback()
    finally:
        db.close()


def verify_otp(db: Session, reg: Registration, otp: str) -> schemas.VerifyOtpResponse:
    from ..providers import get_provider

    provider = get_provider(reg.provider)

    if reg.status != Status.OTP_SENT:
        return schemas.VerifyOtpResponse(
            id=reg.id, phone=reg.phone, status=reg.status,
            message="No OTP is outstanding for this number (still being sent or already resolved).",
        )

    if not otp_valid_window(reg.otp_sent_at):
        reg.status = Status.FAILED
        reg.error = "OTP expired before verification."
        db.commit()
        return schemas.VerifyOtpResponse(
            id=reg.id, phone=reg.phone, status=reg.status, message=reg.error
        )

    if reg.otp_attempts >= MAX_OTP_ATTEMPTS:
        reg.status = Status.FAILED
        reg.error = "Too many OTP attempts."
        db.commit()
        return schemas.VerifyOtpResponse(
            id=reg.id, phone=reg.phone, status=reg.status, message=reg.error
        )

    reg.otp_attempts += 1

    # A test fake may provide a local hash -> validate here.
    # Real SportyBet -> no local hash; the platform validates the operator-typed
    # code inside complete_signup.
    if reg.otp_hash is not None and not check_otp(otp, reg.otp_hash):
        db.commit()
        return schemas.VerifyOtpResponse(
            id=reg.id, phone=reg.phone, status=reg.status, message="Incorrect OTP."
        )

    password = _decrypt_row_password(reg)
    try:
        result = provider.complete_signup(
            phone=reg.phone,
            password=password or "",
            otp=otp,
            provider_ref=reg.provider_ref,
        )
    except Exception as exc:
        logger.exception("Provider completion failure for %s", reg.phone)
        reg.status = Status.FAILED
        reg.error = str(exc)[:500]
        db.commit()
        return schemas.VerifyOtpResponse(
            id=reg.id, phone=reg.phone, status=reg.status, message=reg.error
        )

    if result.verified:
        reg.status = Status.OTP_VERIFIED
        reg.verified_at = dt.datetime.now(dt.timezone.utc)
        reg.error = None
    else:
        reg.status = Status.FAILED
        reg.error = result.error or result.message

    db.commit()
    return schemas.VerifyOtpResponse(
        id=reg.id, phone=reg.phone, status=reg.status, message=result.message
    )


def get_registration(db: Session, reg_id: int) -> schemas.RegistrationOut:
    row = db.get(Registration, reg_id)
    if row is None:
        return None
    return _row_out(row)


def list_registrations(db: Session, status: str | None, limit: int, offset: int) -> list[schemas.RegistrationOut]:
    q = select(Registration).order_by(Registration.created_at.desc())
    if status:
        q = q.where(Registration.status == status)
    rows = db.scalars(q.limit(limit).offset(offset)).all()
    return [_row_out(r) for r in rows]


def delete_registrations(db: Session, ids: list[int]) -> int:
    """Delete registrations by id. Already-running rows are not touched."""
    deleted = 0
    for reg_id in ids:
        reg = db.get(Registration, reg_id)
        if reg is None:
            continue
        db.delete(reg)
        deleted += 1
    db.commit()
    logger.info("deleted %d registration(s)", deleted)
    return deleted


def stats(db: Session) -> schemas.StatsOut:
    from ..config import settings

    total = db.scalar(select(func.count()).select_from(Registration)) or 0
    by_status = dict(db.execute(select(Registration.status, func.count()).group_by(Registration.status)).all())
    return schemas.StatsOut(
        total=total,
        pending=by_status.get(Status.PENDING, 0),
        sending=by_status.get(Status.SENDING, 0),
        otp_sent=by_status.get(Status.OTP_SENT, 0),
        verified=by_status.get(Status.OTP_VERIFIED, 0),
        failed=by_status.get(Status.FAILED, 0),
        provider=settings.provider.lower(),
        password_mode="generated",
    )


# ---------------------------------------------------------------------------
# Queue: bulk add, "next up", approve / skip (with auto-advance).
# ---------------------------------------------------------------------------


def _with_default_country(raw: str, default_country: str) -> str | None:
    """Normalize a pasted/imported number; prepend the default dial code when
    the caller didn't include a supported one. Returns None when unusable."""
    digits = normalize_phone(raw)
    if not digits:
        return None
    if digits.startswith(("234", "254")):
        return digits
    if default_country in ("234", "254"):
        return f"{default_country}{digits}"
    return None


def bulk_create_registrations(
    db: Session,
    numbers: list[str],
    default_country: str = "234",
    manual_sms_select: bool = False,
) -> schemas.BulkImportResponse:
    """Create many registrations at once, tolerating per-row failures.

    Skips rows that already exist (dedup) and rows that fail validation,
    collecting their raw values so the UI can report exactly what didn't land.
    """
    created: list[schemas.RegistrationOut] = []
    skipped: list[str] = []
    errors: list[str] = []

    seen: set[str] = set()
    for raw in numbers:
        phone = _with_default_country(raw, default_country)
        if not phone:
            errors.append(f"{raw}: not a usable phone number")
            continue
        if phone in seen:
            skipped.append(phone)
            continue
        seen.add(phone)
        try:
            created.append(
                create_registration(
                    db=db,
                    phone=phone,
                    password=None,
                    manual_sms_select=manual_sms_select,
                )
            )
        except HTTPException as exc:
            if exc.status_code == 409:  # duplicate/username collision
                skipped.append(phone)
            else:
                errors.append(f"{raw}: {exc.detail}")
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"{raw}: {str(exc)[:120]}")

    return schemas.BulkImportResponse(created=created, skipped=skipped, errors=errors)


def parse_uploaded_contacts(filename: str, data: bytes) -> list[str]:
    """Parse an uploaded contact file into phone-like digit strings."""
    if not data:
        return []
    return parse_contacts(filename, data)


# Statuses that mean "still being worked" — the queue's current contact is the
# earliest row in any of these states.
_UNRESOLVED = [Status.PENDING, Status.SENDING, Status.OTP_SENT]


def queue_next(db: Session) -> schemas.RegistrationOut | None:
    """Return the current contact: the earliest still-unresolved registration."""
    q = (
        select(Registration)
        .where(Registration.status.in_(_UNRESOLVED))
        .order_by(Registration.created_at.asc(), Registration.id.asc())
        .limit(1)
    )
    row = db.scalars(q).first()
    return _row_out(row) if row is not None else None


def _advance_queue(db: Session) -> tuple[schemas.RegistrationOut | None, bool]:
    """Auto-start the next pending contact; report what happened.

    Returns ``(next_out, started)`` — ``started`` is True when a fresh OTP
    request was kicked off for the next line in the queue.
    """
    nxt = db.scalars(
        select(Registration)
        .where(Registration.status == Status.PENDING)
        .order_by(Registration.created_at.asc(), Registration.id.asc())
        .limit(1)
    ).first()
    if nxt is not None:
        request_send_otp(db, nxt)
        return _row_out(nxt), True
    # Nothing pending left to start — surface any still-in-flight contact.
    return queue_next(db), False


def approve_registration(
    db: Session, reg: Registration, advance: bool = True
) -> tuple[schemas.RegistrationOut, schemas.RegistrationOut | None, bool]:
    """Operator approved this contact (OTP confirmed); resolve it, then start
    the next line if ``advance`` is set."""
    if reg.status == Status.OTP_VERIFIED:
        raise HTTPException(status_code=409, detail="This contact is already verified.")
    if reg.status not in (Status.PENDING, Status.SENDING, Status.OTP_SENT, Status.FAILED):
        raise HTTPException(status_code=409, detail=f"Cannot approve a {reg.status!r} contact.")

    reg.status = Status.OTP_VERIFIED
    reg.verified_at = dt.datetime.now(dt.timezone.utc)
    reg.error = None
    db.commit()

    updated = _row_out(reg)
    if not advance:
        return updated, queue_next(db), False
    nxt, started = _advance_queue(db)
    return updated, nxt, started


def skip_registration(
    db: Session, reg: Registration, advance: bool = True
) -> tuple[schemas.RegistrationOut, schemas.RegistrationOut | None, bool]:
    """Operator skipped this contact (it delayed / went stale); mark it failed,
    then start the next line if ``advance`` is set."""
    if reg.status == Status.FAILED:
        raise HTTPException(status_code=409, detail="This contact is already failed/skipped.")
    if reg.status not in (Status.PENDING, Status.SENDING, Status.OTP_SENT):
        raise HTTPException(status_code=409, detail="Cannot skip a resolved contact.")

    reg.status = Status.FAILED
    reg.error = "Skipped by operator."
    db.commit()

    updated = _row_out(reg)
    if not advance:
        return updated, queue_next(db), False
    nxt, started = _advance_queue(db)
    return updated, nxt, started