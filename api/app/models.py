from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Registration(Base):
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    provider: Mapped[str] = mapped_column(String(32), default="sportybet")
    provider_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    otp_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    otp_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    otp_attempts: Mapped[int] = mapped_column(Integer, default=0)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # When True the operator clicks "SMS OTP" themselves in the live browser
    # window instead of the system auto-selecting it.
    manual_sms_select: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=_utcnow
    )