from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .security import Status


class RegisterRequest(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    password: Optional[str] = Field(default=None, max_length=128)
    # True → the operator clicks "SMS OTP" in the browser window themselves;
    # False (default) → the system auto-selects it.
    manual_sms_select: bool = False


class RegistrationOut(BaseModel):
    id: int
    phone: str
    password: Optional[str] = None
    status: str
    provider: str
    provider_ref: Optional[str] = None
    error: Optional[str] = None
    manual_sms_select: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SendOtpResponse(BaseModel):
    id: int
    phone: str
    status: str
    provider_ref: Optional[str] = None
    message: str


class VerifyOtpRequest(BaseModel):
    otp: str = Field(min_length=4, max_length=8)


class VerifyOtpResponse(BaseModel):
    id: int
    phone: str
    status: str
    message: str


class StatsOut(BaseModel):
    total: int
    pending: int
    sending: int
    otp_sent: int
    verified: int
    failed: int
    provider: str
    password_mode: str


class DeleteRegistrationsResponse(BaseModel):
    deleted: int


def to_registration_out(row, *, password: Optional[str] = None) -> RegistrationOut:
    return RegistrationOut(
        id=row.id,
        phone=row.phone,
        password=password,
        status=row.status,
        provider=row.provider,
        provider_ref=row.provider_ref,
        error=row.error,
        manual_sms_select=bool(getattr(row, "manual_sms_select", False)),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


STATUS_ORDER = [Status.PENDING, Status.SENDING, Status.OTP_SENT, Status.OTP_VERIFIED, Status.FAILED]