"""End-to-end tests for the Sporty OTP Lab API using a fake provider.

The app ships without any simulated/demo provider. These tests register a
lightweight ``FakeProvider`` (test hook in ``app.providers``) that behaves like
SportyBet would: it "delivers" a code out-of-band and validates it during
complete_signup, so no browser and no real SMS are involved.
"""
import base64
import os
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["PROVIDER"] = "fake"
os.environ["DATABASE_URL"] = "sqlite:///./test_sporty.db"
os.environ["OTP_TTL_SECONDS"] = "300"
os.environ["API_TOKEN"] = "test-token"

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.providers import register_provider  # noqa: E402
from app.providers.base import CompleteResult, ProviderAdapter, SendContext, SendResult  # noqa: E402

FAKE_OTP = "471293"


class FakeProvider(ProviderAdapter):
    """Stand-in for SportyBet: accepts any phone, "texts" a fixed code."""

    name = "fake"
    code = FAKE_OTP

    def send_otp(self, ctx: SendContext) -> SendResult:
        return SendResult(
            success=True,
            message=f"Fake OTP delivered to {ctx.phone}.",
            provider_ref=f"fake-{ctx.phone}",
        )

    def complete_signup(self, phone: str, password: str, otp: str, provider_ref: str | None) -> CompleteResult:
        ok = otp == self.code
        return CompleteResult(
            success=ok,
            verified=ok,
            message="Verified" if ok else "Incorrect OTP.",
            error=None if ok else "Incorrect OTP.",
        )


register_provider("fake", FakeProvider)

engine = create_engine("sqlite:///./test_sporty.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.headers.update({"Authorization": "Bearer test-token"})
    return client


def test_register_nigeria_generates_credentials():
    client = _client()
    res = client.post("/api/registrations", json={"phone": "+234 801 234 5678"})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "pending"
    assert body["phone"] == "2348012345678"
    assert body.get("demootp") is None
    assert "demootp" not in body
    pw = body["password"]
    assert len(pw) >= 8
    assert any(c.isupper() for c in pw)
    assert any(c.islower() for c in pw)
    assert any(c.isdigit() for c in pw)
    assert any(not c.isalnum() for c in pw)


def test_register_uses_supplied_password():
    client = _client()
    res = client.post("/api/registrations", json={"phone": "2348012345678", "password": "MyCustomPass1!"})
    assert res.status_code == 201, res.text
    assert res.json()["password"] == "MyCustomPass1!"


def test_short_password_rejected():
    client = _client()
    res = client.post("/api/registrations", json={"phone": "2348012345678", "password": "short"})
    assert res.status_code == 422


def test_register_kenya_accepted():
    client = _client()
    res = client.post("/api/registrations", json={"phone": "+254 712 345 678"})
    assert res.status_code == 201, res.text
    assert res.json()["phone"] == "254712345678"


def test_only_kenya_and_nigeria_supported():
    client = _client()
    res = client.post("/api/registrations", json={"phone": "+1 202 555 0100"})
    assert res.status_code == 422
    assert "Kenya" in res.json()["detail"]


def test_duplicate_phone_conflicts():
    client = _client()
    client.post("/api/registrations", json={"phone": "2348012345678"})
    res = client.post("/api/registrations", json={"phone": "2348012345678"})
    assert res.status_code == 409


def test_invalid_phone_rejected():
    client = _client()
    res = client.post("/api/registrations", json={"phone": "123"})
    assert res.status_code == 422


def _wait_otp_sent(client, reg_id):
    row = None
    for _ in range(30):
        row = client.get(f"/api/registrations/{reg_id}").json()
        if row["status"] in ("otp_sent", "otp_verified", "failed"):
            break
        time.sleep(0.2)
    return row


def test_full_fake_flow():
    client = _client()
    res = client.post("/api/registrations", json={"phone": "254712345678"})
    reg = res.json()

    sent = client.post(f"/api/registrations/{reg['id']}/send-otp")
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["status"] == "sending"
    assert "demootp" not in body

    row = _wait_otp_sent(client, reg["id"])
    assert row["status"] == "otp_sent", row

    verify = client.post(f"/api/registrations/{reg['id']}/verify-otp", json={"otp": FAKE_OTP})
    assert verify.status_code == 200
    assert verify.json()["status"] == "otp_verified"


def test_wrong_otp_rejected():
    client = _client()
    reg = client.post("/api/registrations", json={"phone": "2348012345678"}).json()
    client.post(f"/api/registrations/{reg['id']}/send-otp")
    row = _wait_otp_sent(client, reg["id"])
    assert row["status"] == "otp_sent", row
    res = client.post(f"/api/registrations/{reg['id']}/verify-otp", json={"otp": "000000"})
    assert res.status_code == 200
    assert res.json()["status"] != "otp_verified"


def test_stats():
    client = _client()
    client.post("/api/registrations", json={"phone": "2348012345678"})
    client.post("/api/registrations", json={"phone": "2547098765432"})
    res = client.get("/api/stats")
    assert res.status_code == 200
    assert res.json()["total"] == 2
    assert res.json()["pending"] == 2
    assert res.json()["provider"] == "fake"


def test_auth_required():
    client = _client()
    client.headers.clear()
    assert client.get("/api/registrations").status_code == 401


def test_delete():
    client = _client()
    reg = client.post("/api/registrations", json={"phone": "2348012345678"}).json()
    res = client.delete(f"/api/registrations/{reg['id']}")
    assert res.status_code == 200
    assert res.json()["deleted"] == 1
    assert client.get(f"/api/registrations/{reg['id']}").status_code == 404


def test_bulk_create_with_dedupe_and_errors():
    client = _client()
    res = client.post(
        "/api/registrations/bulk",
        json={
            "numbers": ["2348012345678", "+234 803 000 1111", "8011234567", "123", "2348012345678"],
            "default_country": "234",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    # 3 usable, 1 duplicate skipped, 1 too-short row reported as an error.
    assert len(body["created"]) == 3
    assert body["skipped"] == ["2348012345678"]
    assert len(body["errors"]) == 1
    assert "123" in body["errors"][0]
    assert {c["phone"] for c in body["created"]} == {"2348012345678", "2348030001111", "2348011234567"}


def test_queue_next_picks_earliest_pending():
    client = _client()
    a = client.post("/api/registrations", json={"phone": "2348012345678"}).json()
    b = client.post("/api/registrations", json={"phone": "2348023456789"}).json()
    res = client.get("/api/queue/next")
    assert res.status_code == 200
    assert res.json()["current"]["id"] == a["id"]


def test_skip_advances_and_starts_next():
    client = _client()
    a = client.post("/api/registrations", json={"phone": "2348012345678"}).json()
    b = client.post("/api/registrations", json={"phone": "2348023456789"}).json()

    res = client.post(f"/api/registrations/{a['id']}/skip", json={"advance": True})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["updated"]["status"] == "failed"
    assert body["updated"]["error"] == "Skipped by operator."
    assert body["next"]["id"] == b["id"]
    assert body["next_started"] is True
    # The next one was auto-started by _advance_queue -> now sending/otp_sent.
    assert body["next"]["status"] in ("sending", "otp_sent")


def test_approve_advances_and_starts_next():
    client = _client()
    a = client.post("/api/registrations", json={"phone": "2348012345678"}).json()
    b = client.post("/api/registrations", json={"phone": "2348023456789"}).json()

    res = client.post(f"/api/registrations/{a['id']}/approve", json={"advance": True})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["updated"]["status"] == "otp_verified"
    assert body["next"]["id"] == b["id"]
    assert body["next_started"] is True


def test_import_csv_creates_rows():
    client = _client()
    csv_data = "phone,name\n+254 712 300 100,Alice\n254 700 200 100,Bob\n"
    b64 = base64.b64encode(csv_data.encode()).decode()
    res = client.post(
        "/api/registrations/import",
        json={"filename": "contacts.csv", "data_base64": b64, "default_country": "254"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["created"]) == 2
    assert {c["phone"] for c in body["created"]} == {"254712300100", "254700200100"}


def test_import_unsupported_extension_rejected():
    client = _client()
    res = client.post(
        "/api/registrations/import",
        json={"filename": "contacts.pdf", "data_base64": "bW9jaA==", "default_country": "234"},
    )
    assert res.status_code == 400