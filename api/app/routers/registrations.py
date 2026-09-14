from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..models import Registration
from ..services import registration as svc

router = APIRouter(prefix="/api", tags=["registrations"])

_IMPORT_EXTENSIONS = {".csv", ".txt", ".tsv", ".xlsx", ".xls"}


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
        manual_sms_select=payload.manual_sms_select,
    )


@router.post("/registrations/bulk", response_model=schemas.BulkImportResponse)
def bulk_create(payload: schemas.BulkRegisterRequest, db: Session = Depends(get_db)):
    """Add many numbers at once (pasted list or parsed file rows)."""
    return svc.bulk_create_registrations(
        db=db,
        numbers=payload.numbers,
        default_country=payload.default_country,
        manual_sms_select=payload.manual_sms_select,
    )


@router.post("/registrations/import", response_model=schemas.BulkImportResponse)
def import_contacts(payload: schemas.ImportRequest, db: Session = Depends(get_db)):
    """Import contacts from a file the client already read (base64-encoded).

    No multipart dependency needed: the browser sends ``{filename, data_base64,
    default_country}`` as plain JSON and we decode + parse server-side.
    """
    import base64
    import os

    name = (payload.filename or "").lower()
    ext = os.path.splitext(name)[1]
    if ext not in _IMPORT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext or 'none'}'. Use .csv, .txt, .tsv, .xlsx or .xls.",
        )
    try:
        data = base64.b64decode(payload.data_base64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="File data is not valid base64.") from exc
    if len(data) > 4 * 1024 * 1024:  # 4 MiB cap
        raise HTTPException(status_code=413, detail="File too large (max 4 MiB).")

    numbers = svc.parse_uploaded_contacts(name, data)
    if not numbers:
        raise HTTPException(status_code=422, detail="No phone numbers could be read from the file.")

    return svc.bulk_create_registrations(
        db=db,
        numbers=numbers,
        default_country=payload.default_country,
        manual_sms_select=payload.manual_sms_select,
    )


@router.get("/queue/next", response_model=schemas.QueueResponse)
def queue_next(db: Session = Depends(get_db)):
    """The current contact the operator should be working on."""
    return schemas.QueueResponse(current=svc.queue_next(db))


@router.post("/registrations/{reg_id}/approve", response_model=schemas.ApproveSkipResponse)
def approve_registration(
    reg_id: int,
    payload: schemas.ApproveSkipRequest,
    db: Session = Depends(get_db),
):
    reg = _get_registration(db, reg_id)
    updated, nxt, started = svc.approve_registration(db, reg, advance=payload.advance)
    return schemas.ApproveSkipResponse(updated=updated, next=nxt, next_started=started)


@router.post("/registrations/{reg_id}/skip", response_model=schemas.ApproveSkipResponse)
def skip_registration(
    reg_id: int,
    payload: schemas.ApproveSkipRequest,
    db: Session = Depends(get_db),
):
    reg = _get_registration(db, reg_id)
    updated, nxt, started = svc.skip_registration(db, reg, advance=payload.advance)
    return schemas.ApproveSkipResponse(updated=updated, next=nxt, next_started=started)


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