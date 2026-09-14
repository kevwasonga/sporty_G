from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..models import Registration
from ..services import registration as svc

router = APIRouter(prefix="/api", tags=["registrations"])


def _get_registration(db: Session, reg_id: int) -> Registration:
    reg = db.get(Registration, reg_id)
    if reg is None:
        raise HTTPException(status_code=404, detail="Registration not found")
    return reg


@router.post("/registrations", response_model=schemas.RegistrationOut, status_code=201)
def create_registration(payload: schemas.RegisterRequest, db: Session = Depends(get_db)):
    return svc.create_registration(
        db=db,
        phone=payload.phone,
        password=(payload.password.strip() or None) if payload.password else None,
    )


@router.get("/registrations", response_model=list[schemas.RegistrationOut])
def list_registrations(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return svc.list_registrations(db, status=status, limit=page_size, offset=(page - 1) * page_size)


@router.get("/registrations/{reg_id}", response_model=schemas.RegistrationOut)
def get_registration(reg_id: int, db: Session = Depends(get_db)):
    row = svc.get_registration(db, reg_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Registration not found")
    return row


@router.post("/registrations/{reg_id}/send-otp", response_model=schemas.SendOtpResponse)
def send_otp(reg_id: int, db: Session = Depends(get_db)):
    reg = _get_registration(db, reg_id)
    return svc.request_send_otp(db, reg)


@router.post("/registrations/{reg_id}/verify-otp", response_model=schemas.VerifyOtpResponse)
def verify_otp(reg_id: int, payload: schemas.VerifyOtpRequest, db: Session = Depends(get_db)):
    reg = _get_registration(db, reg_id)
    return svc.verify_otp(db, reg, payload.otp)


@router.delete("/registrations/{reg_id}", response_model=schemas.DeleteRegistrationsResponse)
def delete_registration(reg_id: int, db: Session = Depends(get_db)):
    _get_registration(db, reg_id)
    deleted = svc.delete_registrations(db, [reg_id])
    return schemas.DeleteRegistrationsResponse(deleted=deleted)


@router.get("/stats", response_model=schemas.StatsOut)
def stats(db: Session = Depends(get_db)):
    return svc.stats(db)